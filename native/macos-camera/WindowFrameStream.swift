import Foundation
import ScreenCaptureKit
import CoreMedia
import CoreVideo
import CoreImage

/// One persistent ScreenCaptureKit stream; hold only the latest complete frame.
final class WindowFrameStream: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private var latest: (CVPixelBuffer, Double)?
    private var failure: Error?
    private var captureStream: SCStream?
    private let context = CIContext(options: [.cacheIntermediates: false])

    func start(window: SCWindow, fps: Double) async throws {
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        let width = Double(filter.contentRect.width) * Double(filter.pointPixelScale)
        let height = Double(filter.contentRect.height) * Double(filter.pointPixelScale)
        let factor = min(1, 4096 / max(width, height))
        config.width = max(2, Int(width * factor))
        config.height = max(2, Int(height * factor))
        // Keep capture fresh even when uploads are configured below one FPS.
        config.minimumFrameInterval = CMTime(seconds: 1 / max(1, fps), preferredTimescale: 600)
        config.queueDepth = 3
        config.pixelFormat = kCVPixelFormatType_32BGRA
        config.showsCursor = false
        config.capturesAudio = false
        config.ignoreShadowsSingleWindow = true
        config.shouldBeOpaque = true
        let stream = SCStream(filter: filter, configuration: config, delegate: self)
        try stream.addStreamOutput(self, type: .screen, sampleHandlerQueue: DispatchQueue(label: "skillforge.capture.frames"))
        captureStream = stream
        try await stream.startCapture()
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .screen, sampleBuffer.isValid,
              let attachments = CMSampleBufferGetSampleAttachmentsArray(sampleBuffer, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
              let raw = attachments.first?[.status] as? Int,
              SCFrameStatus(rawValue: raw) == .complete,
              let buffer = sampleBuffer.imageBuffer else { return }
        lock.lock()
        latest = (buffer, Date().timeIntervalSince1970)
        lock.unlock()
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        lock.lock(); failure = error; latest = nil; lock.unlock()
    }

    func frame(maxAge: Double) throws -> (CGImage, Double)? {
        lock.lock(); let saved = latest; let error = failure; lock.unlock()
        if let error { throw error }
        guard let (buffer, capturedAt) = saved else { return nil }
        guard Date().timeIntervalSince1970 - capturedAt <= maxAge else {
            return nil // Wait for a new callback; never re-date or upload an old frame.
        }
        let image = CIImage(cvPixelBuffer: buffer)
        guard let cg = context.createCGImage(image, from: image.extent) else {
            throw CaptureFailure(message: "Could not convert the captured window frame.")
        }
        return (cg, capturedAt)
    }

    func stop() async {
        if let captureStream { try? await captureStream.stopCapture() }
        captureStream = nil
    }
}
