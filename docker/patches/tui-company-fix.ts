import { Global } from "../../global"
import { Provider } from "../../provider/provider"
import { Server } from "../../server/server"
import { bootstrap } from "../bootstrap"
import { UI } from "../ui"
import { cmd } from "./cmd"
import path from "path"
import fs from "fs/promises"
import { Installation } from "../../installation"
import { Config } from "../../config/config"
import { Bus } from "../../bus"
import { Log } from "../../util/log"
import { FileWatcher } from "../../file/watch"
import { Ide } from "../../ide"

import { Flag } from "../../flag/flag"
import { Session } from "../../session"

declare global {
  const OPENCODE_TUI_PATH: string
}

if (typeof OPENCODE_TUI_PATH !== "undefined") {
  await import(OPENCODE_TUI_PATH as string, {
    with: { type: "file" },
  })
}

export const TuiCommand = cmd({
  command: "$0 [project]",
  describe: "start opencode tui",
  builder: (yargs) =>
    yargs
      .positional("project", {
        type: "string",
        describe: "path to start opencode in",
      })
      .option("model", {
        type: "string",
        alias: ["m"],
        describe: "model to use in the format of provider/model",
      })
      .option("continue", {
        alias: ["c"],
        describe: "continue the last session",
        type: "boolean",
      })
      .option("session", {
        alias: ["s"],
        describe: "session id to continue",
        type: "string",
      })
      .option("prompt", {
        alias: ["p"],
        type: "string",
        describe: "prompt to use",
      })
      .option("agent", {
        type: "string",
        describe: "agent to use",
      })
      .option("port", {
        type: "number",
        describe: "port to listen on",
        default: 0,
      })
      .option("hostname", {
        alias: ["h"],
        type: "string",
        describe: "hostname to listen on",
        default: "127.0.0.1",
      }),
  handler: async (args) => {
    while (true) {
      const cwd = args.project ? path.resolve(args.project) : process.cwd()
      try {
        process.chdir(cwd)
      } catch (e) {
        UI.error("Failed to change directory to " + cwd)
        return
      }
      const result = await bootstrap({ cwd }, async (app) => {
        const sessionID = await (async () => {
          if (args.continue) {
            const it = Session.list()
            try {
              for await (const s of it) {
                if (s.parentID === undefined) {
                  return s.id
                }
              }
              return
            } finally {
              await it.return()
            }
          }
          if (args.session) {
            return args.session
          }
          return undefined
        })()
        FileWatcher.init()
        const providers = await Provider.list()
        if (Object.keys(providers).length === 0) {
          return "needs_provider"
        }

        const server = Server.listen({
          port: args.port,
          hostname: args.hostname,
        })

        // Company Fix: Look for pre-built TUI binary in multiple locations
        let cmd = ["go", "run", "./main.go"]
        let cwd = Bun.fileURLToPath(new URL("../../../../tui/cmd/opencode", import.meta.url))

        // First, check for environment variable pointing to TUI binary
        if (process.env.OPENCODE_TUI_BINARY) {
          const binaryPath = process.env.OPENCODE_TUI_BINARY
          // Verify the binary exists before using it
          try {
            await fs.access(binaryPath, fs.constants.X_OK)
            cmd = [binaryPath]
            cwd = process.cwd()
            console.log("[Company] Using TUI binary from env:", binaryPath)
          } catch (e) {
            console.error("[Company] TUI binary specified in env not found:", binaryPath)
          }
        }

        // If not found via env or env not set, check for TUI binary in known locations
        if (cmd[0] === "go") {
          const possiblePaths = [
            // In Docker container - prioritize x64
            "/home/bun/.cache/opencode/tui/tui-linux-x64",
            "/usr/local/bin/opencode-tui",
            "/home/bun/.cache/opencode/tui/tui-linux-arm64",
            // In development
            path.join(Global.Path.cache, "tui", "tui-linux-x64"),
            path.join(Global.Path.cache, "tui", "tui-linux-arm64"),
            // Relative to opencode binary
            path.join(path.dirname(process.execPath), "tui-linux-x64"),
            path.join(path.dirname(process.execPath), "tui-linux-arm64"),
          ]

          // Select appropriate binary based on architecture
          const arch = process.arch === "x64" || process.arch === "x86_64" ? "x64" : "arm64"
          const platform = process.platform
          const binaryName = `tui-${platform}-${arch}`

          // Add platform-specific binary to search paths
          possiblePaths.unshift(
            path.join(Global.Path.cache, "tui", binaryName),
            `/home/bun/.cache/opencode/tui/${binaryName}`
          )

          for (const binaryPath of possiblePaths) {
            try {
              await fs.access(binaryPath, fs.constants.X_OK)
              // Test if we can actually execute it
              const testProc = Bun.spawn([binaryPath, "--help"], {
                stdout: "pipe",
                stderr: "pipe",
              })
              const exitCode = await testProc.exited
              if (exitCode === 0 || exitCode === 2) { // 2 is ok for --help with flags
                cmd = [binaryPath]
                cwd = process.cwd()
                console.log("[Company] Found working TUI binary at:", binaryPath)
                break
              }
            } catch (e) {
              // Continue searching
              console.log("[Company] Skipping non-working binary:", binaryPath, e.message)
            }
          }
        }

        // Fallback to embedded files (original OpenCode behavior)
        const tui = Bun.embeddedFiles.find((item) => (item as File).name.includes("tui")) as File
        if (tui) {
          let binaryName = tui.name
          if (process.platform === "win32" && !binaryName.endsWith(".exe")) {
            binaryName += ".exe"
          }
          const binary = path.join(Global.Path.cache, "tui", binaryName)
          const file = Bun.file(binary)
          if (!(await file.exists())) {
            await Bun.write(file, tui, { mode: 0o755 })
            await fs.chmod(binary, 0o755)
          }
          cwd = process.cwd()
          cmd = [binary]
        }

        // If still using go run, log an error
        if (cmd[0] === "go") {
          console.error("[Company] ERROR: TUI binary not found. TUI mode will not work.")
          console.error("[Company] Please ensure TUI binary is installed at one of these locations:")
          console.error("  - /home/bun/.cache/opencode/tui/tui-linux-x64")
          console.error("  - Set OPENCODE_TUI_BINARY environment variable")
          UI.error("TUI binary not found. Please check the installation.")
          return "done"
        }

        Log.Default.info("tui", {
          cmd,
        })
        const proc = Bun.spawn({
          cmd: [
            ...cmd,
            ...(args.model ? ["--model", args.model] : []),
            ...(args.prompt ? ["--prompt", args.prompt] : []),
            ...(args.agent ? ["--agent", args.agent] : []),
            ...(sessionID ? ["--session", sessionID] : []),
          ],
          cwd,
          stdout: "inherit",
          stderr: "inherit",
          stdin: "inherit",
          env: {
            ...process.env,
            CGO_ENABLED: "0",
            OPENCODE_SERVER: server.url.toString(),
            OPENCODE_APP_INFO: JSON.stringify(app),
          },
          onExit: () => {
            server.stop()
          },
        })

        ;(async () => {
          if (Installation.isDev()) return
          if (Installation.isSnapshot()) return
          const config = await Config.global()
          if (config.autoupdate === false || Flag.OPENCODE_DISABLE_AUTOUPDATE) return
          const latest = await Installation.latest().catch(() => {})
          if (!latest) return
          if (Installation.VERSION === latest) return
          const method = await Installation.method()
          if (method === "unknown") return
          await Installation.upgrade(method, latest)
            .then(() => Bus.publish(Installation.Event.Updated, { version: latest }))
            .catch(() => {})
        })()
        ;(async () => {
          if (Ide.alreadyInstalled()) return
          const ide = Ide.ide()
          if (ide === "unknown") return
          await Ide.install(ide)
            .then(() => Bus.publish(Ide.Event.Installed, { ide }))
            .catch(() => {})
        })()

        await proc.exited
        server.stop()

        return "done"
      })
      if (result === "done") break
      if (result === "needs_provider") {
        UI.empty()
        UI.println(UI.logo("   "))
        const result = await Bun.spawn({
          cmd: [...getOpencodeCommand(), "auth", "login"],
          cwd: process.cwd(),
          stdout: "inherit",
          stderr: "inherit",
          stdin: "inherit",
        }).exited
        if (result !== 0) return
        UI.empty()
      }
    }
  },
})

/**
 * Get the correct command to run opencode CLI
 * In development: ["bun", "run", "packages/opencode/src/index.ts"]
 * In production: ["/path/to/opencode"]
 */
function getOpencodeCommand(): string[] {
  // Check if OPENCODE_BIN_PATH is set (used by shell wrapper scripts)
  if (process.env["OPENCODE_BIN_PATH"]) {
    return [process.env["OPENCODE_BIN_PATH"]]
  }

  const execPath = process.execPath.toLowerCase()

  if (Installation.isDev()) {
    // In development, use bun to run the TypeScript entry point
    return [execPath, "run", process.argv[1]]
  }

  // In production, use the current executable path
  return [process.execPath]
}
