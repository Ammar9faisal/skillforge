import AppKit
import ScreenCaptureKit
import AVFoundation
import Darwin

struct RecorderError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}
final class RecorderState: NSObject, SCRecordingOutputDelegate, SCStreamDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private var shouldStop = false
    private var complete = false
    private var error: String?
    func stop() { lock.lock(); shouldStop = true; lock.unlock() }
    func status() -> (Bool, Bool, String?) { lock.lock(); defer { lock.unlock() }; return (shouldStop, complete, error) }
    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) { print("Recording the selected SkillForge window only (silent). Ctrl+C / SIGTERM saves and stops."); fflush(stdout) }
    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) { lock.lock(); complete = true; lock.unlock() }
    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) { fail(error) }
    func stream(_ stream: SCStream, didStopWithError error: Error) { fail(error) }
    func fail(_ failure: Error) { lock.lock(); error = failure.localizedDescription; shouldStop = true; lock.unlock() }
}
@main struct RecordDemo {
    @MainActor static func main() async {
        NSApplication.shared.setActivationPolicy(.prohibited)
        do {
            guard CGPreflightScreenCaptureAccess() else { throw RecorderError(message: "Screen Recording permission is required for this launching app/helper.") }
            let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: false)
            let windows = content.windows.filter {
                $0.owningApplication?.bundleIdentifier == "com.apple.Safari" &&
                ($0.title ?? "").contains("SkillForge") && $0.frame.width > 500
            }
            let args = Array(CommandLine.arguments.dropFirst())
            if args == ["--list"] {
                for w in windows { print("\(w.windowID): \(Int(w.frame.width))x\(Int(w.frame.height)) \(w.title ?? "")") }
                return
            }
            guard args.count == 2, let id = UInt32(args[0]), let window = windows.first(where: { $0.windowID == id }) else {
                throw RecorderError(message: "Usage: record-demo.sh --list, then record-demo.sh WINDOW_ID NEW_OUTPUT.mp4. Only Safari SkillForge windows are accepted.")
            }
            let output = URL(fileURLWithPath: args[1])
            guard !FileManager.default.fileExists(atPath: output.path) else { throw RecorderError(message: "Output exists; choose a new filename.") }
            let state = RecorderState()
            let filter = SCContentFilter(desktopIndependentWindow: window)
            let config = SCStreamConfiguration()
            let factor = min(1, 1600 / filter.contentRect.width)
            config.width = max(2, Int(filter.contentRect.width * factor) / 2 * 2)
            config.height = max(2, Int(filter.contentRect.height * factor) / 2 * 2)
            config.minimumFrameInterval = CMTime(value: 1, timescale: 15)
            config.capturesAudio = false
            config.captureMicrophone = false
            config.showsCursor = true
            config.ignoreShadowsSingleWindow = true
            let recordingConfig = SCRecordingOutputConfiguration()
            recordingConfig.outputURL = output
            recordingConfig.videoCodecType = .h264
            recordingConfig.outputFileType = .mp4
            let recording = SCRecordingOutput(configuration: recordingConfig, delegate: state)
            let stream = SCStream(filter: filter, configuration: config, delegate: state)
            try stream.addRecordingOutput(recording)
            let signals = [SIGINT, SIGTERM].map { number -> DispatchSourceSignal in
                signal(number, SIG_IGN)
                let source = DispatchSource.makeSignalSource(signal: number, queue: .global())
                source.setEventHandler { state.stop() }; source.resume(); return source
            }
            defer { signals.forEach { $0.cancel() } }
            try await stream.startCapture()
            let started = Date()
            while !state.status().0 && Date().timeIntervalSince(started) < 1800 {
                try await Task.sleep(nanoseconds: 200_000_000)
            }
            try await stream.stopCapture()
            let deadline = Date().addingTimeInterval(10)
            while !state.status().1 && state.status().2 == nil && Date() < deadline {
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            if let error = state.status().2 { throw RecorderError(message: error) }
            guard state.status().1 else { throw RecorderError(message: "Recording did not finalize within ten seconds; inspect the file before using it.") }
            print("Saved: \(output.path) — \(CMTimeGetSeconds(recording.recordedDuration)) seconds, \(recording.recordedFileSize) bytes. Review before sharing.")
        } catch {
            FileHandle.standardError.write(Data("Recording error: \(error.localizedDescription)\n".utf8)); exit(1)
        }
    }
}
