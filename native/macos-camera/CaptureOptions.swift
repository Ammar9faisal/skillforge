import CoreGraphics
import Foundation

struct CaptureFailure: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

struct Crop {
    let x: Double, y: Double, width: Double, height: Double
    static let full = Crop(x: 0, y: 0, width: 1, height: 1)
    init(x: Double, y: Double, width: Double, height: Double) {
        self.x = x; self.y = y; self.width = width; self.height = height
    }
    init(_ text: String) throws {
        let parts = text.split(separator: ",", omittingEmptySubsequences: false).compactMap { Double($0) }
        guard parts.count == 4, parts.allSatisfy({ $0.isFinite }),
              parts[0] >= 0, parts[1] >= 0, parts[2] > 0, parts[3] > 0,
              parts[0] + parts[2] <= 1.000001, parts[1] + parts[3] <= 1.000001 else {
            throw CaptureFailure(message: "Crop must be normalized top-left x,y,width,height, within 0…1 (for example 0.05,0.10,0.90,0.80).")
        }
        self.init(x: parts[0], y: parts[1], width: parts[2], height: parts[3])
    }
    func rectangle(width pixelsWide: Int, height pixelsHigh: Int) -> CGRect {
        // Avoid a spurious extra pixel from values such as (0.2 + 0.4) * 1000.
        let left = floor(x * Double(pixelsWide) + 1e-9), top = floor(y * Double(pixelsHigh) + 1e-9)
        let right = min(Double(pixelsWide), ceil((x + width) * Double(pixelsWide) - 1e-9))
        let bottom = min(Double(pixelsHigh), ceil((y + height) * Double(pixelsHigh) - 1e-9))
        return CGRect(x: left, y: top, width: right - left, height: bottom - top)
    }
}

struct Options {
    var command = "help"
    var windowID: CGWindowID?
    var select = false
    var all = false
    var requestPermission = false
    var crop = Crop.full
    var output: String?
    var fps = 2.0
    var backend = "http://127.0.0.1:8000"
    var maxWidth = 1280
    var quality = 0.85
    init(_ arguments: [String]) throws {
        if let first = arguments.first { command = first }
        var i = 1
        while i < arguments.count {
            let flag = arguments[i]
            func value() throws -> String {
                i += 1
                guard i < arguments.count else { throw CaptureFailure(message: "Missing value for \(flag).") }
                return arguments[i]
            }
            switch flag {
            case "--window-id":
                guard let id = UInt32(try value()), id > 0 else { throw CaptureFailure(message: "Invalid window ID.") }
                windowID = id
            case "--select": select = true
            case "--all": all = true
            case "--request": requestPermission = true
            case "--crop": crop = try Crop(value())
            case "--output": output = try value()
            case "--fps":
                guard let rate = Double(try value()), rate.isFinite, rate >= 0.2, rate <= 10 else { throw CaptureFailure(message: "FPS must be between 0.2 and 10.") }
                fps = rate
            case "--backend": backend = try value()
            case "--max-width":
                guard let pixels = Int(try value()), (160...4096).contains(pixels) else { throw CaptureFailure(message: "Max width must be 160…4096 pixels.") }
                maxWidth = pixels
            case "--quality":
                guard let q = Double(try value()), q.isFinite, (0.1...1).contains(q) else { throw CaptureFailure(message: "JPEG quality must be 0.1…1.") }
                quality = q
            default: throw CaptureFailure(message: "Unknown option: \(flag). Use help.")
            }
            i += 1
        }
    }
}

