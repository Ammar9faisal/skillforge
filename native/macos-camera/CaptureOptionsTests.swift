import Foundation

@main
struct CaptureOptionsTests {
    static func main() throws {
        var checks = 0
        func check(_ value: Bool, _ name: String) {
            guard value else { fatalError("Failed: \(name)") }
            checks += 1
        }
        func rejects(_ args: [String]) {
            do { _ = try Options(args); fatalError("Expected rejection: \(args)") }
            catch { checks += 1 }
        }
        let defaults = try Options(["snapshot"])
        check(defaults.fps == 2, "default upload rate")
        check(defaults.maxWidth == 1280 && defaults.quality == 0.85, "bounded JPEG defaults")
        let selected = try Options(["snapshot", "--window-id", "123", "--crop", "0.1,0.2,0.5,0.4", "--output", "/tmp/test.jpg"])
        check(selected.windowID == 123, "stable window ID")
        let rect = selected.crop.rectangle(width: 2000, height: 1000)
        check(rect.origin.x == 200 && rect.origin.y == 200 && rect.width == 1000 && rect.height == 400, "normalized top-left crop")
        let full = Crop.full.rectangle(width: 1920, height: 1080)
        check(full.width == 1920 && full.height == 1080, "full-window crop")
        let fractional = try Crop("0.001,0.001,0.5,0.5").rectangle(width: 101, height: 99)
        check(fractional.minX >= 0 && fractional.maxX <= 101 && fractional.maxY <= 99, "fractional rounding stays in image")
        for crop in ["", "0,0,1", "0,0,1,1,0", "-0.1,0,1,1", "0,0,0,1", "0,0,1,-1", "0.5,0,0.6,1", "nan,0,1,1", "0,0,inf,1"] {
            rejects(["snapshot", "--crop", crop])
        }
        for rate in ["0", "-1", "11", "NaN", "inf", "abc"] { rejects(["stream", "--fps", rate]) }
        for id in ["-1", "0", "not-an-id", "4294967296"] { rejects(["snapshot", "--window-id", id]) }
        rejects(["snapshot", "--output"])
        rejects(["list", "--unknown"])
        rejects(["snapshot", "--quality", "1.1"])
        rejects(["snapshot", "--max-width", "0"])
        let stream = try Options(["stream", "--fps", "2.5", "--backend", "http://127.0.0.1:9000", "--select"])
        check(stream.fps == 2.5 && stream.select && stream.backend.hasSuffix(":9000"), "stream options")
        for backend in ["http://example.com:8000", "http://127.0.0.1:8000/path", "http://user@localhost:8000", "http://localhost:8000?token=test", "file:///tmp/frame"] {
            do { _ = try FrameForwarder(backend: backend); check(false, "reject remote or unsafe backend") }
            catch { check(true, "reject remote or unsafe backend") }
        }
        let local = try FrameForwarder(backend: "http://127.0.0.1:8000")
        check(local.base.host == "127.0.0.1", "loopback backend")
        local.session.invalidateAndCancel()
        let staleBody = try JSONSerialization.data(withJSONObject: ["detail": "Capture timestamp is stale or in the future. Capture a new frame."])
        if case .staleFrame = FrameForwarder.rejection(path: "frame", status: 409, data: staleBody) { check(true, "stale frame is recoverable") }
        else { check(false, "stale frame is recoverable") }
        let sequenceBody = try JSONSerialization.data(withJSONObject: ["detail": "Duplicate or out-of-order frame rejected."])
        let sequenceError = FrameForwarder.rejection(path: "frame", status: 409, data: sequenceBody)
        check(sequenceError.localizedDescription.contains("sequence conflict"), "sequence errors remain fatal and specific")
        let secretBody = try JSONSerialization.data(withJSONObject: ["detail": "secret-response-token"])
        check(!FrameForwarder.rejection(path: "frame", status: 409, data: secretBody).localizedDescription.contains("secret-response-token"), "unknown response bodies stay private")
        if case .rejected = FrameForwarder.rejection(path: "start", status: 409, data: staleBody) { check(true, "start conflict is not silently retried") }
        else { check(false, "start conflict is not silently retried") }
        print("\(checks) native option/crop checks passed. No screen capture or network used.")
    }
}
