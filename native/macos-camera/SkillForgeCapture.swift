import AppKit
import CoreGraphics
import Foundation
import ScreenCaptureKit
import Darwin

@main
struct SkillForgeCapture {
    static let permissionHelp = "Enable Screen Recording (Screen & System Audio Recording on recent macOS) for the launching app/helper in System Settings → Privacy & Security. When launching from VS Code, macOS may attribute access to Code or the helper. Reopen the launching app if macOS asks, then run permission again. No developer account is required."

    static func isWhatsApp(_ window: SCWindow) -> Bool {
        let app = window.owningApplication
        return app?.bundleIdentifier.lowercased().contains("whatsapp") == true || app?.applicationName.lowercased() == "whatsapp"
    }

    static func windows() async throws -> [SCWindow] {
        guard CGPreflightScreenCaptureAccess() else { throw CaptureFailure(message: "Screen Recording permission is missing. Run ./native/macos-camera/run.sh permission --request. \(permissionHelp)") }
        // Include covered/off-screen windows; do not enumerate only visible windows.
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: false)
        return content.windows.filter { $0.frame.width >= 40 && $0.frame.height >= 40 }
            .sorted { $0.windowID < $1.windowID }
    }

    static func describe(_ window: SCWindow) -> String {
        let app = window.owningApplication?.applicationName ?? "Unknown"
        let bundle = window.owningApplication?.bundleIdentifier ?? ""
        let title = (window.title ?? "(untitled)").replacingOccurrences(of: "\n", with: " ")
        return "id=\(window.windowID) app=\(app) [\(bundle)] size=\(Int(window.frame.width))×\(Int(window.frame.height)) onScreen=\(window.isOnScreen) title=\(title)"
    }

    static func choose(_ options: Options) async throws -> SCWindow {
        let matches = try await windows().filter(isWhatsApp)
        guard !matches.isEmpty else { throw CaptureFailure(message: "No WhatsApp windows found. Open WhatsApp and its video-call window, then list again.") }
        if let id = options.windowID {
            guard let match = matches.first(where: { $0.windowID == id }) else { throw CaptureFailure(message: "Selected WhatsApp window no longer exists. List windows and select a new ID; capture will never switch windows automatically.") }
            return match
        }
        if options.select {
            for (index, window) in matches.enumerated() { print("\(index + 1). \(describe(window))") }
            print("Choose the incoming-video call window number: ", terminator: "")
            guard let text = readLine(), let selection = Int(text), matches.indices.contains(selection - 1) else { throw CaptureFailure(message: "Invalid selection. Use --window-id ID from list.") }
            return matches[selection - 1]
        }
        guard matches.count == 1 else { throw CaptureFailure(message: "Multiple WhatsApp windows exist. Use --select or --window-id ID from list; refusing to guess the call window.") }
        return matches[0]
    }

    static func capture(_ window: SCWindow, options: Options) async throws -> Data {
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        let scale = Double(filter.pointPixelScale)
        let nativeWidth = Double(filter.contentRect.width) * scale
        let nativeHeight = Double(filter.contentRect.height) * scale
        let bound = min(1.0, 4096.0 / max(nativeWidth, nativeHeight))
        config.width = max(1, Int((nativeWidth * bound).rounded()))
        config.height = max(1, Int((nativeHeight * bound).rounded()))
        config.showsCursor = false
        config.capturesAudio = false
        config.ignoreShadowsSingleWindow = true
        config.shouldBeOpaque = true
        let fullImage = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
        return try jpeg(fullImage, options: options)
    }

    static func jpeg(_ fullImage: CGImage, options: Options) throws -> Data {
        let rect = options.crop.rectangle(width: fullImage.width, height: fullImage.height)
        guard rect.width >= 2, rect.height >= 2, let cropped = fullImage.cropping(to: rect) else {
            throw CaptureFailure(message: "Crop is empty at the captured resolution. Choose a larger region.")
        }
        let factor = min(1.0, Double(options.maxWidth) / Double(cropped.width))
        let width = max(1, Int(Double(cropped.width) * factor))
        let height = max(1, Int(Double(cropped.height) * factor))
        guard let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                                      space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else {
            throw CaptureFailure(message: "Could not allocate JPEG conversion buffer.")
        }
        context.interpolationQuality = .high
        context.draw(cropped, in: CGRect(x: 0, y: 0, width: width, height: height))
        guard let image = context.makeImage(), let jpeg = NSBitmapImageRep(cgImage: image).representation(using: .jpeg, properties: [.compressionFactor: options.quality]) else {
            throw CaptureFailure(message: "Could not encode captured window as JPEG.")
        }
        return jpeg
    }

    static func stream(_ options: Options) async throws {
        let destination = try FrameForwarder(backend: options.backend)
        let selected = try await choose(options)
        let selectedPID = selected.owningApplication?.processID
        let size = selected.frame.size
        let frames = WindowFrameStream()
        try await frames.start(window: selected, fps: options.fps)
        let token: String
        do {
            let deadline = Date().addingTimeInterval(5)
            while try frames.frame(maxAge: 3) == nil {
                guard Date() < deadline else { throw CaptureFailure(message: "No complete window frame received within five seconds.") }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            token = try await destination.start(options: options, windowID: selected.windowID)
        } catch { await frames.stop(); throw error }
        let stop = StopFlag()
        let signals = [SIGINT, SIGTERM].map { number -> DispatchSourceSignal in
            signal(number, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: number, queue: .global())
            source.setEventHandler { stop.stop() }
            source.resume()
            return source
        }
        defer { for source in signals { source.cancel() }; destination.session.invalidateAndCancel() }
        print("Forwarding cropped WhatsApp window \(selected.windowID) to \(options.backend) at up to \(options.fps) FPS. Select WhatsApp Ray-Bans in SkillForge. Ctrl+C stops. No frames are saved to disk.")
        fflush(stdout)
        var count = 0
        var acceptedCount = 0
        var lastAccepted = ProcessInfo.processInfo.systemUptime
        var delayedFrames = 0
        do {
            while !stop.stopped {
                let iteration = ProcessInfo.processInfo.systemUptime
                guard let current = try await windows().first(where: { $0.windowID == selected.windowID && $0.owningApplication?.processID == selectedPID }) else {
                    throw CaptureFailure(message: "Selected call window closed. List windows and explicitly select a new ID; no alternate window was captured.")
                }
                guard current.frame.size == size else {
                    throw CaptureFailure(message: "Call window resized. Recheck the snapshot/crop and restart the helper to avoid capturing the wrong region.")
                }
                guard let (image, capturedAt) = try frames.frame(maxAge: 1.5) else {
                    guard ProcessInfo.processInfo.systemUptime - lastAccepted < max(5, 3 / options.fps) else {
                        throw CaptureFailure(message: "The call window stopped providing fresh frames. Check the call and restart the helper.")
                    }
                    try await Task.sleep(nanoseconds: 100_000_000)
                    continue
                }
                let jpeg = try jpeg(image, options: options)
                if stop.stopped { break }
                count += 1
                do {
                    _ = try await destination.post("frame", body: jpeg, token: token, sequence: count, capturedAt: capturedAt)
                    lastAccepted = ProcessInfo.processInfo.systemUptime
                    acceptedCount += 1
                    delayedFrames = 0
                } catch FrameUploadError.staleFrame {
                    delayedFrames += 1
                    guard delayedFrames < 5 else {
                        throw CaptureFailure(message: "Five frames arrived too late. Check backend load and lower --max-width (for example 960), then restart the helper.")
                    }
                    print("Discarded a delayed frame; waiting for a fresh capture.")
                    fflush(stdout)
                    try await Task.sleep(nanoseconds: UInt64(1_000_000_000 / options.fps))
                    continue
                }
                if acceptedCount == 1 || acceptedCount % max(1, Int(options.fps * 5)) == 0 {
                    print("Forwarded \(acceptedCount) fresh cropped frames (last JPEG \(jpeg.count) bytes).")
                    fflush(stdout)
                }
                let remaining = max(0, 1.0 / options.fps - (ProcessInfo.processInfo.systemUptime - iteration))
                if remaining > 0 { try await Task.sleep(nanoseconds: UInt64(remaining * 1_000_000_000)) }
            }
        } catch {
            await frames.stop()
            _ = try? await destination.post("stop", token: token)
            throw error
        }
        await frames.stop()
        _ = try? await destination.post("stop", token: token)
        print("Native forwarding stopped; backend frames invalidated. USB source remains available.")
    }

    @MainActor static func main() async {
        // Initialize AppKit's WindowServer connection for command-line JPEG work.
        // Prohibited activation keeps the helper out of the Dock and foreground.
        NSApplication.shared.setActivationPolicy(.prohibited)
        do {
            let options = try Options(Array(CommandLine.arguments.dropFirst()))
            switch options.command {
            case "help", "--help", "-h":
                print("""
                SkillForge native WhatsApp window capture — macOS 14+
                ./native/macos-camera/run.sh permission [--request]
                ./native/macos-camera/run.sh list [--all]
                ./native/macos-camera/run.sh snapshot --window-id ID --output /tmp/rayban.jpg [--crop x,y,w,h]
                ./native/macos-camera/run.sh stream --window-id ID --crop x,y,w,h [--fps 2] [--backend http://127.0.0.1:8000]
                Window selection: --select prompts when multiple WhatsApp windows exist.
                Crop uses normalized top-left coordinates relative to the whole window, not desktop pixels.
                JPEG: --max-width 1280 --quality 0.85. No audio is captured.
                """)
            case "permission":
                let allowed = options.requestPermission ? CGRequestScreenCaptureAccess() : CGPreflightScreenCaptureAccess()
                print(allowed ? "Screen Recording permission is available." : "Screen Recording permission is not available. \(permissionHelp)")
                if !allowed { Foundation.exit(2) }
            case "list":
                let available = try await windows()
                let matches = options.all ? available : available.filter(isWhatsApp)
                for window in matches { print(describe(window)) }
                if matches.isEmpty { throw CaptureFailure(message: "No matching windows. Open WhatsApp and its video call, then retry.") }
            case "stream":
                try await stream(options)
            case "snapshot":
                guard let output = options.output else { throw CaptureFailure(message: "snapshot requires --output PATH; no frames are saved by default.") }
                let window = try await choose(options)
                let jpeg = try await capture(window, options: options)
                try jpeg.write(to: URL(fileURLWithPath: output), options: .atomic)
                print("Saved JPEG (\(jpeg.count) bytes) from WhatsApp window \(window.windowID) to \(output).")
            default: throw CaptureFailure(message: "Unknown command: \(options.command). Use help.")
            }
        } catch {
            FileHandle.standardError.write(Data("Capture error: \(error.localizedDescription)\n".utf8))
            Foundation.exit(1)
        }
    }
}
