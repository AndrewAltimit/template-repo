//! Procedural macros for MCP server tool registration.
//!
//! This crate provides the `#[mcp_tool]` attribute macro for automatically
//! generating tool implementations from async functions.
//!
//! # Example
//!
//! ```rust,ignore
//! use mcp_macros::mcp_tool;
//!
//! #[mcp_tool(description = "Echo the input message")]
//! async fn echo(
//!     #[mcp(description = "Message to echo")]
//!     message: String,
//! ) -> Result<String> {
//!     Ok(format!("Echo: {}", message))
//! }
//! ```
//!
//! This generates a struct `EchoTool` that implements the `Tool` trait.

use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::{format_ident, quote};
use syn::{
    Attribute, FnArg, Ident, ItemFn, Lit, Meta, Pat, ReturnType, Type, parse_macro_input,
    punctuated::Punctuated, token::Comma,
};

/// Attribute macro for defining MCP tools.
///
/// # Attributes
///
/// - `description`: Tool description (required)
/// - `name`: Override tool name (defaults to function name)
///
/// # Parameter Attributes
///
/// Parameters can have `#[mcp(...)]` attributes:
/// - `description`: Parameter description
/// - `default`: Default value (makes parameter optional); the literal keeps its
///   JSON type (`default = 1` is an integer, `default = "x"` a string)
/// - `state`: Inject this parameter from the generated struct's fields instead
///   of deserializing it from the JSON arguments. State parameters are excluded
///   from the input schema and must be `Clone`. When any parameter is marked
///   `state`, the macro generates a fielded struct with a `new(...)`
///   constructor (in declaration order) instead of a unit struct.
///
/// Plain parameters are required; `Option<T>` parameters are optional. Missing
/// or wrong-typed arguments produce an `InvalidParameters` error rather than a
/// panic.
///
/// # Example
///
/// ```rust,ignore
/// #[mcp_tool(description = "Search for items")]
/// async fn search(
///     #[mcp(state)]
///     store: Arc<Store>,                // injected, not from JSON
///     #[mcp(description = "Search query")]
///     query: String,
///     #[mcp(description = "Max results", default = 10)]
///     limit: Option<i32>,
/// ) -> Result<Vec<Item>, anyhow::Error> {
///     // Implementation; `store` is `self.store.clone()`
/// }
/// // Register with: `.tool(SearchTool::new(store.clone()))`
/// ```
#[proc_macro_attribute]
pub fn mcp_tool(attr: TokenStream, item: TokenStream) -> TokenStream {
    let attrs = parse_macro_input!(attr as ToolAttrs);
    let func = parse_macro_input!(item as ItemFn);

    match generate_tool(attrs, func) {
        Ok(tokens) => tokens.into(),
        Err(e) => e.to_compile_error().into(),
    }
}

struct ToolAttrs {
    description: String,
    name: Option<String>,
}

impl syn::parse::Parse for ToolAttrs {
    fn parse(input: syn::parse::ParseStream) -> syn::Result<Self> {
        let mut description = None;
        let mut name = None;

        let metas: Punctuated<Meta, Comma> = Punctuated::parse_terminated(input)?;

        for meta in metas {
            if let Meta::NameValue(nv) = meta {
                let ident = nv.path.get_ident().map(|i| i.to_string());
                match ident.as_deref() {
                    Some("description") => {
                        if let syn::Expr::Lit(syn::ExprLit {
                            lit: Lit::Str(s), ..
                        }) = &nv.value
                        {
                            description = Some(s.value());
                        }
                    },
                    Some("name") => {
                        if let syn::Expr::Lit(syn::ExprLit {
                            lit: Lit::Str(s), ..
                        }) = &nv.value
                        {
                            name = Some(s.value());
                        }
                    },
                    _ => {},
                }
            }
        }

        Ok(ToolAttrs {
            description: description.unwrap_or_else(|| "No description".to_string()),
            name,
        })
    }
}

struct ParamInfo {
    name: Ident,
    ty: Type,
    description: Option<String>,
    /// Default value literal, preserved as a `Lit` so its JSON type (integer,
    /// string, bool, ...) survives into the generated schema and extraction.
    default: Option<Lit>,
    is_optional: bool,
    /// Marked `#[mcp(state)]`: injected from the generated struct's fields
    /// (e.g. a shared store or HTTP client) rather than deserialized from the
    /// JSON arguments. Such params are excluded from the schema.
    is_state: bool,
}

fn generate_tool(attrs: ToolAttrs, func: ItemFn) -> syn::Result<TokenStream2> {
    let func_name = &func.sig.ident;
    let tool_name = attrs.name.unwrap_or_else(|| func_name.to_string());
    let tool_struct_name = format_ident!("{}Tool", to_pascal_case(&tool_name));
    let description = &attrs.description;

    // Parse parameters
    let params = parse_params(&func)?;

    // Generate JSON schema for parameters
    let schema = generate_schema(&params);

    // Generate argument extraction
    let arg_extraction = generate_arg_extraction(&params);

    // execute_impl keeps every parameter (state + args) in the original order.
    let param_names: Vec<_> = params.iter().map(|p| &p.name).collect();
    let param_types: Vec<_> = params.iter().map(|p| &p.ty).collect();

    // State parameters (`#[mcp(state)]`) become struct fields populated by a
    // generated `new(...)` constructor; everything else is deserialized from the
    // JSON arguments at call time.
    let state_params: Vec<&ParamInfo> = params.iter().filter(|p| p.is_state).collect();
    let state_names: Vec<_> = state_params.iter().map(|p| &p.name).collect();
    let state_types: Vec<_> = state_params.iter().map(|p| &p.ty).collect();

    // Build the execute_impl call arguments in declaration order: state values
    // are cloned out of `self`, arg values come from the deserialized locals.
    let call_args: Vec<TokenStream2> = params
        .iter()
        .map(|p| {
            let name = &p.name;
            if p.is_state {
                quote! { self.#name.clone() }
            } else {
                quote! { #name }
            }
        })
        .collect();

    // Keep the original function but make it a method
    let func_body = &func.block;
    let func_output = &func.sig.output;

    let output_type = match func_output {
        ReturnType::Default => quote! { () },
        ReturnType::Type(_, ty) => quote! { #ty },
    };

    // With no state, keep the ergonomic unit struct (`MyTool`); with state,
    // generate a fielded struct plus a `new(...)` constructor.
    let struct_def = if state_params.is_empty() {
        quote! {
            #[doc = concat!("Generated MCP tool for `", stringify!(#func_name), "`.")]
            pub struct #tool_struct_name;
        }
    } else {
        quote! {
            #[doc = concat!("Generated MCP tool for `", stringify!(#func_name), "`.")]
            pub struct #tool_struct_name {
                #(#state_names: #state_types,)*
            }

            impl #tool_struct_name {
                #[doc = "Construct the tool with its injected state."]
                pub fn new(#(#state_names: #state_types,)*) -> Self {
                    Self { #(#state_names,)* }
                }
            }
        }
    };

    Ok(quote! {
        #struct_def

        impl #tool_struct_name {
            async fn execute_impl(#(#param_names: #param_types,)*) -> #output_type
            #func_body
        }

        #[async_trait::async_trait]
        impl mcp_core::tool::Tool for #tool_struct_name {
            fn name(&self) -> &str {
                #tool_name
            }

            fn description(&self) -> &str {
                #description
            }

            fn schema(&self) -> serde_json::Value {
                #schema
            }

            async fn execute(&self, args: serde_json::Value) -> mcp_core::error::Result<mcp_core::tool::ToolResult> {
                #arg_extraction

                match Self::execute_impl(#(#call_args,)*).await {
                    Ok(result) => mcp_core::tool::ToolResult::json(&result),
                    Err(e) => Ok(mcp_core::tool::ToolResult::error(e.to_string())),
                }
            }
        }
    })
}

fn parse_params(func: &ItemFn) -> syn::Result<Vec<ParamInfo>> {
    let mut params = Vec::new();

    for arg in &func.sig.inputs {
        if let FnArg::Typed(pat_type) = arg
            && let Pat::Ident(pat_ident) = &*pat_type.pat
        {
            let name = pat_ident.ident.clone();
            let ty = (*pat_type.ty).clone();

            // Check if type is Option<T>
            let is_optional = is_option_type(&ty);

            // Parse #[mcp(...)] attributes
            let (description, default, is_state) = parse_param_attrs(&pat_type.attrs);

            params.push(ParamInfo {
                name,
                ty,
                description,
                default,
                is_optional,
                is_state,
            });
        }
    }

    Ok(params)
}

fn parse_param_attrs(attrs: &[Attribute]) -> (Option<String>, Option<Lit>, bool) {
    let mut description = None;
    let mut default = None;
    let mut is_state = false;

    for attr in attrs {
        if attr.path().is_ident("mcp") {
            let _ = attr.parse_nested_meta(|meta| {
                if meta.path.is_ident("description") {
                    let value: syn::LitStr = meta.value()?.parse()?;
                    description = Some(value.value());
                } else if meta.path.is_ident("default") {
                    // Preserve the literal so the generated `json!(...)` keeps the
                    // correct JSON type (e.g. `1` -> integer, not the string "1").
                    default = Some(meta.value()?.parse::<Lit>()?);
                } else if meta.path.is_ident("state") {
                    // Flag form: `#[mcp(state)]` (no value).
                    is_state = true;
                }
                Ok(())
            });
        }
    }

    (description, default, is_state)
}

fn is_option_type(ty: &Type) -> bool {
    if let Type::Path(type_path) = ty
        && let Some(segment) = type_path.path.segments.last()
    {
        return segment.ident == "Option";
    }
    false
}

fn generate_schema(params: &[ParamInfo]) -> TokenStream2 {
    let mut properties = Vec::new();
    let mut required = Vec::new();

    for param in params {
        if param.is_state {
            continue;
        }
        let name = param.name.to_string();
        let description = param.description.as_deref().unwrap_or("");
        let json_type = rust_type_to_json_type(&param.ty);

        properties.push(quote! {
            #name: {
                "type": #json_type,
                "description": #description
            }
        });

        if !param.is_optional && param.default.is_none() {
            required.push(name);
        }
    }

    quote! {
        serde_json::json!({
            "type": "object",
            "properties": {
                #(#properties),*
            },
            "required": [#(#required),*]
        })
    }
}

fn generate_arg_extraction(params: &[ParamInfo]) -> TokenStream2 {
    let extractions: Vec<_> = params
        .iter()
        .filter(|p| !p.is_state)
        .map(|p| {
            let name = &p.name;
            let ty = &p.ty;
            let name_str = name.to_string();

            // Each parameter is bound to its *declared* type by deserializing the
            // corresponding JSON value via serde. A type mismatch or a missing
            // required parameter becomes a clean `InvalidParameters` error rather
            // than a panic, which is the whole point of the typed macro path.
            if p.is_optional {
                // `Option<T>`: an absent key deserializes from `null` -> `None`.
                quote! {
                    let #name: #ty = serde_json::from_value(
                        args.get(#name_str).cloned().unwrap_or(serde_json::Value::Null)
                    ).map_err(|e| mcp_core::error::MCPError::InvalidParameters(
                        format!("Invalid parameter '{}': {}", #name_str, e)
                    ))?;
                }
            } else if let Some(default) = &p.default {
                quote! {
                    let #name: #ty = serde_json::from_value(
                        args.get(#name_str).cloned().unwrap_or_else(|| serde_json::json!(#default))
                    ).map_err(|e| mcp_core::error::MCPError::InvalidParameters(
                        format!("Invalid parameter '{}': {}", #name_str, e)
                    ))?;
                }
            } else {
                quote! {
                    let #name: #ty = serde_json::from_value(
                        args.get(#name_str).cloned().ok_or_else(|| {
                            mcp_core::error::MCPError::InvalidParameters(
                                format!("Missing required parameter: {}", #name_str)
                            )
                        })?
                    ).map_err(|e| mcp_core::error::MCPError::InvalidParameters(
                        format!("Invalid parameter '{}': {}", #name_str, e)
                    ))?;
                }
            }
        })
        .collect();

    quote! {
        #(#extractions)*
    }
}

fn rust_type_to_json_type(ty: &Type) -> &'static str {
    if let Type::Path(type_path) = ty
        && let Some(segment) = type_path.path.segments.last()
    {
        let ident = segment.ident.to_string();
        return match ident.as_str() {
            "String" | "str" => "string",
            "i8" | "i16" | "i32" | "i64" | "u8" | "u16" | "u32" | "u64" | "isize" | "usize" => {
                "integer"
            },
            "f32" | "f64" => "number",
            "bool" => "boolean",
            "Vec" => "array",
            "Option" => {
                // For Option<T>, return the inner type
                if let syn::PathArguments::AngleBracketed(args) = &segment.arguments
                    && let Some(syn::GenericArgument::Type(inner)) = args.args.first()
                {
                    return rust_type_to_json_type(inner);
                }
                "string"
            },
            _ => "object",
        };
    }
    "string"
}

fn to_pascal_case(s: &str) -> String {
    let mut result = String::new();
    let mut capitalize_next = true;

    for c in s.chars() {
        if c == '_' || c == '-' {
            capitalize_next = true;
        } else if capitalize_next {
            result.push(c.to_ascii_uppercase());
            capitalize_next = false;
        } else {
            result.push(c);
        }
    }

    result
}
