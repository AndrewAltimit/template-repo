import companyModels from "../company-models.json"
import { z } from "zod"

export namespace ModelsDev {
  export const Model = z
    .object({
      id: z.string(),
      name: z.string(),
      release_date: z.string(),
      attachment: z.boolean(),
      reasoning: z.boolean(),
      temperature: z.boolean(),
      tool_call: z.boolean(),
      cost: z.object({
        input: z.number(),
        output: z.number(),
        cache_read: z.number().optional(),
        cache_write: z.number().optional(),
      }),
      limit: z.object({
        context: z.number(),
        output: z.number(),
      }),
      options: z.record(z.any()),
    })
    .openapi({ ref: "Model" })

  export const Provider = z
    .object({
      api: z.string().optional(),
      name: z.string(),
      env: z.array(z.string()),
      id: z.string(),
      npm: z.string().optional(),
      models: z.record(Model),
    })
    .openapi({ ref: "Provider" })

  export type Model = z.infer<typeof Model>
  export type Provider = z.infer<typeof Provider>

  export async function get() {
    console.log("[Company] Using Company models: company/claude-3.5-sonnet, company/claude-3-opus, company/gpt-4")
    return companyModels as Record<string, Provider>
  }

  export async function refresh() {
    console.log("[Company] Static configuration")
  }
}
