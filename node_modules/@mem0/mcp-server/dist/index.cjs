#!/usr/bin/env node
"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// src/index.ts
var import_server = require("@modelcontextprotocol/sdk/server/index.js");
var import_stdio = require("@modelcontextprotocol/sdk/server/stdio.js");
var import_types = require("@modelcontextprotocol/sdk/types.js");
var import_mem0ai = require("mem0ai");
var import_dotenv = __toESM(require("dotenv"), 1);
import_dotenv.default.config();
var MEM0_API_KEY = process?.env?.MEM0_API_KEY || "";
var memoryClient = new import_mem0ai.MemoryClient({ apiKey: MEM0_API_KEY });
var ADD_MEMORY_TOOL = {
  name: "add-memory",
  description: "Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevent information whcih can be useful in the future conversation. This can also be called when the user asks you to remember something.",
  inputSchema: {
    type: "object",
    properties: {
      content: {
        type: "string",
        description: "The content to store in memory"
      },
      userId: {
        type: "string",
        description: "User ID for memory storage. If not provided explicitly, use a generic user ID like, 'mem0-mcp-user'"
      }
    },
    required: ["content", "userId"]
  }
};
var SEARCH_MEMORIES_TOOL = {
  name: "search-memories",
  description: "Search through stored memories. This method is called ANYTIME the user asks anything.",
  inputSchema: {
    type: "object",
    properties: {
      query: {
        type: "string",
        description: "The search query. This is the query that the user has asked for. Example: 'What did I tell you about the weather last week?' or 'What did I tell you about my friend John?'"
      },
      userId: {
        type: "string",
        description: "User ID for memory storage. If not provided explicitly, use a generic user ID like, 'mem0-mcp-user'"
      }
    },
    required: ["query", "userId"]
  }
};
var server = new import_server.Server(
  {
    name: "mem0-mcp",
    version: "0.0.1"
  },
  {
    capabilities: {
      tools: {},
      logging: {}
    }
  }
);
async function addMemory(content, userId) {
  try {
    const messages = [
      { role: "system", content: "Memory storage system" },
      { role: "user", content }
    ];
    await memoryClient.add(messages, { user_id: userId });
    return true;
  } catch (error) {
    console.error("Error adding memory:", error);
    return false;
  }
}
async function searchMemories(query, userId) {
  try {
    const results = await memoryClient.search(query, { user_id: userId });
    return results;
  } catch (error) {
    console.error("Error searching memories:", error);
    return [];
  }
}
server.setRequestHandler(import_types.ListToolsRequestSchema, async () => ({
  tools: [ADD_MEMORY_TOOL, SEARCH_MEMORIES_TOOL]
}));
server.setRequestHandler(import_types.CallToolRequestSchema, async (request) => {
  try {
    const { name, arguments: args } = request.params;
    if (!args) {
      throw new Error("No arguments provided");
    }
    switch (name) {
      case "add-memory": {
        const { content, userId } = args;
        await addMemory(content, userId);
        return {
          content: [
            {
              type: "text",
              text: "Memory added successfully"
            }
          ],
          isError: false
        };
      }
      case "search-memories": {
        const { query, userId } = args;
        const results = await searchMemories(query, userId);
        const formattedResults = results.map(
          (result) => `Memory: ${result.memory}
Relevance: ${result.score}
---`
        ).join("\n");
        return {
          content: [
            {
              type: "text",
              text: formattedResults || "No memories found"
            }
          ],
          isError: false
        };
      }
      default:
        return {
          content: [
            { type: "text", text: `Unknown tool: ${name}` }
          ],
          isError: true
        };
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error instanceof Error ? error.message : String(error)}`
        }
      ],
      isError: true
    };
  }
});
function safeLog(level, data) {
  console.error(`[${level}] ${typeof data === "object" ? JSON.stringify(data) : data}`);
  try {
    server.sendLoggingMessage({ level, data });
  } catch (error) {
  }
}
async function main() {
  try {
    console.error("Initializing Mem0 Memory MCP Server...");
    const transport = new import_stdio.StdioServerTransport();
    await server.connect(transport);
    safeLog("info", "Mem0 Memory MCP Server initialized successfully");
    console.error("Memory MCP Server running on stdio");
  } catch (error) {
    console.error("Fatal error running server:", error);
    process.exit(1);
  }
}
main().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});
//# sourceMappingURL=index.cjs.map