"use strict";
const fs = require("node:fs"),
  path = require("node:path"),
  os = require("node:os"),
  http = require("node:http");
class Service {
  constructor(directory) {
    this.directory =
      directory ||
      [
        path.join(os.homedir(), ".local/share/supersurfer/state"),
        path.join(os.homedir(), ".supersurfer"),
      ].find((p) => fs.existsSync(path.join(p, "service.json")));
    if (!this.directory)
      throw new Error(
        "Open SuperSurfer on this host first, or set its state directory.",
      );
  }
  request(route, body) {
    return new Promise((resolve, reject) => {
      let port, token;
      try {
        port = JSON.parse(
          fs.readFileSync(path.join(this.directory, "service.json")),
        ).port;
        token = fs
          .readFileSync(path.join(this.directory, "token"), "utf8")
          .trim();
        if (
          !Number.isInteger(port) ||
          port < 1 ||
          port > 65535 ||
          !token ||
          /[\r\n]/.test(token)
        )
          throw new Error();
      } catch {
        return reject(
          new Error("Cannot read the SuperSurfer service connection."),
        );
      }
      const data =
        body === undefined ? null : Buffer.from(JSON.stringify(body));
      const req = http.request(
        {
          hostname: "127.0.0.1",
          port,
          path: route,
          method: data ? "POST" : "GET",
          headers: {
            Authorization: "Bearer " + token,
            ...(data
              ? {
                  "Content-Type": "application/json",
                  "Content-Length": data.length,
                }
              : {}),
          },
        },
        (res) => {
          let text = "";
          res.on("data", (c) => {
            text += c;
            if (text.length > 16 * 1024 * 1024)
              req.destroy(
                new Error("SuperSurfer response exceeds the size limit."),
              );
          });
          res.on("end", () => {
            try {
              const result = JSON.parse(text);
              if (res.statusCode !== 200)
                throw new Error(result.error || "SuperSurfer request failed");
              resolve(result);
            } catch (e) {
              reject(new Error(e.message.split(token).join("[redacted]")));
            }
          });
        },
      );
      req.setTimeout(30000, () =>
        req.destroy(new Error("SuperSurfer is taking too long to respond.")),
      );
      req.on("error", () =>
        reject(new Error("Cannot reach the SuperSurfer service on this host.")),
      );
      req.end(data);
    });
  }
  action(op, params) {
    return this.request("/api/action", { op, params });
  }
  native(op, params) {
    return this.action("native." + op, params);
  }
  board(binding) {
    return this.native("board", { scope: binding.scope });
  }
}
module.exports = { Service };
