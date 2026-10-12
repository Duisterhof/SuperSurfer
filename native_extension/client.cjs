"use strict";
const http = require("node:http");
function call(config, op, args = {}) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ op, args });
    const req = http.request(
      {
        socketPath: config.socket,
        path: "/",
        method: "POST",
        headers: {
          Authorization: "Bearer " + config.secret,
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data),
        },
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
          if (body.length > 16 * 1024 * 1024) req.destroy();
        });
        res.on("end", () => {
          try {
            const result = JSON.parse(body);
            if (res.statusCode !== 200)
              throw new Error(result.error || "Request failed");
            resolve(result);
          } catch (e) {
            reject(e);
          }
        });
      },
    );
    req.on("error", reject);
    req.setTimeout(35000, () =>
      req.destroy(new Error("SuperSurfer is taking too long to respond.")),
    );
    req.end(data);
  });
}
module.exports = { call };
