import Foundation

final class LocalOnlySession: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping @Sendable (URLRequest?) -> Void) {
        completionHandler(nil) // Never redirect captured images or the lease token elsewhere.
    }
}

final class StopFlag: @unchecked Sendable {
    private let lock = NSLock()
    private var value = false
    func stop() { lock.lock(); value = true; lock.unlock() }
    var stopped: Bool { lock.lock(); defer { lock.unlock() }; return value }
}

enum FrameUploadError: LocalizedError {
    case staleFrame
    case rejected(String)
    var errorDescription: String? {
        switch self {
        case .staleFrame: return "Capture timestamp is stale or in the future. Waiting for a new live frame."
        case .rejected(let message): return message
        }
    }
}

struct FrameForwarder {
    static func rejection(path: String, status: Int, data: Data) -> FrameUploadError {
        let detail = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        let message = detail?["detail"] as? String
        // Recognize only known backend messages; never print arbitrary response bodies.
        if path == "frame", status == 409,
           message == "Capture timestamp is stale or in the future. Capture a new frame." {
            return .staleFrame
        }
        let known: [String: String] = [
            "Duplicate or out-of-order frame rejected.": "Frame sequence conflict. Stop other helpers and restart this helper.",
            "A WhatsApp helper is already sending frames. Stop it before starting another.": "Another helper is active. Stop it before starting a new helper.",
            "Native capture session is invalid. Restart the helper.": "Backend session expired or restarted. Restart the helper.",
            "JPEG exceeds the 4 MB frame limit.": "JPEG is too large. Reduce --max-width or --quality.",
            "JPEG dimensions exceed the 4096-pixel / 8-megapixel limit.": "JPEG dimensions are too large. Reduce --max-width."
        ]
        let reason = message.flatMap { known[$0] } ?? "Check the backend and restart the helper if needed."
        return .rejected("Backend rejected \(path) (HTTP \(status)). \(reason)")
    }

    let base: URL
    let session: URLSession
    let delegate = LocalOnlySession()
    init(backend: String) throws {
        guard let parts = URLComponents(string: backend), let url = parts.url,
              ["http", "https"].contains(parts.scheme ?? ""),
              ["localhost", "127.0.0.1", "[::1]", "::1"].contains(parts.host ?? ""),
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path.isEmpty || parts.path == "/" else {
            throw CaptureFailure(message: "--backend must be a loopback base URL such as http://127.0.0.1:8000. Remote destinations and redirects are not allowed.")
        }
        self.base = url
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 3
        config.timeoutIntervalForResource = 4
        config.httpShouldSetCookies = false
        self.session = URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
    }
    func post(_ path: String, body: Data? = nil, token: String? = nil, sequence: Int? = nil, capturedAt: Double? = nil) async throws -> Data {
        var request = URLRequest(url: base.appendingPathComponent("api/camera/whatsapp/" + path))
        request.httpMethod = "POST"
        request.httpBody = body
        request.setValue("no-store", forHTTPHeaderField: "Cache-Control")
        request.setValue(path == "frame" ? "image/jpeg" : "application/json", forHTTPHeaderField: "Content-Type")
        if let token { request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization") }
        if let sequence { request.setValue(String(sequence), forHTTPHeaderField: "X-Sequence") }
        if let capturedAt { request.setValue(String(capturedAt), forHTTPHeaderField: "X-Captured-At") }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw Self.rejection(path: path, status: status, data: data)
        }
        return data
    }
    func start(options: Options, windowID: UInt32) async throws -> String {
        let crop = options.crop
        let body = try JSONSerialization.data(withJSONObject: ["window_id": windowID,
            "crop": [crop.x, crop.y, crop.width, crop.height], "fps": options.fps])
        let response = try await post("start", body: body)
        guard let object = try JSONSerialization.jsonObject(with: response) as? [String: Any],
              let token = object["upload_token"] as? String, !token.isEmpty else {
            throw CaptureFailure(message: "Backend returned an invalid native-capture session.")
        }
        return token
    }
}
