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
//! ) -> Result<String, anyhow::Error> {
//!     Ok(format!("Echo: {}", message))
//! }
//! ```
//!
//! This generates a struct `EchoTool` that implements the `Tool` trait. The
//! generated code only refers to `mcp_core` (it re-exports what it needs), so
//! the calling crate does not have to depend on `serde_json` or `async-trait`
//! directly.

use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::{format_ident, quote, quote_spanned};
use serde_json::{Map, Value, json};
use syn::{
    Attribute, Expr, ExprLit, FnArg, GenericArgument, Ident, ItemFn, Lit, LitStr, Meta, Pat,
    PathArguments, ReturnType, Type, ext::IdentExt, parse_macro_input, punctuated::Punctuated,
    spanned::Spanned, token::Comma,
};

/// Attribute macro for defining MCP tools.
///
/// # Attributes
///
/// - `description`: Tool description. If omitted, the function's `///` doc
///   comment is used; one of the two is required.
/// - `name`: Override tool name (defaults to function name). Must match
///   `[A-Za-z0-9_.-]{1,128}`.
///
/// # Parameter Attributes
///
/// Parameters can have `#[mcp(...)]` attributes:
/// - `description`: Parameter description
/// - `default`: Default value (makes parameter optional); the value keeps its
///   JSON type (`default = 1` is an integer, `default = "x"` a string,
///   `default = -1` a negative integer) and is advertised in the schema
/// - `state`: Inject this parameter from the generated struct's fields instead
///   of deserializing it from the JSON arguments. State parameters are excluded
///   from the input schema and must be `Clone`. When any parameter is marked
///   `state`, the macro generates a fielded struct with a `new(...)`
///   constructor (in declaration order) instead of a unit struct.
///
/// Plain parameters are required; `Option<T>` parameters are optional. Missing
/// or wrong-typed arguments produce an `InvalidParameters` error rather than a
/// panic. Raw identifiers map to their plain JSON key (`r#type` -> `"type"`).
///
/// # Return value
///
/// The function must return `Result<T, E>` with `E: Display`:
/// - `T = String`: returned as plain text content
/// - `T = ToolResult`: returned as-is (images, multiple blocks, custom errors)
/// - `T = ()`: returned as the text `OK`
/// - any other `T: Serialize`: returned as pretty-printed JSON text
///
/// `Err(e)` becomes an `isError` result carrying `e.to_string()`.
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
///     limit: Option<i32>,               // Some(10) when absent
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
    description: Option<String>,
    name: Option<LitStr>,
}

fn expect_str(value: &Expr, key: &str) -> syn::Result<LitStr> {
    match value {
        Expr::Lit(ExprLit {
            lit: Lit::Str(s), ..
        }) => Ok(s.clone()),
        other => Err(syn::Error::new(
            other.span(),
            format!("`{key}` must be a string literal"),
        )),
    }
}

impl syn::parse::Parse for ToolAttrs {
    fn parse(input: syn::parse::ParseStream) -> syn::Result<Self> {
        let mut description = None;
        let mut name = None;

        let metas: Punctuated<Meta, Comma> = Punctuated::parse_terminated(input)?;

        for meta in metas {
            let Meta::NameValue(nv) = &meta else {
                return Err(syn::Error::new(
                    meta.span(),
                    "expected `key = \"value\"` (supported keys: description, name)",
                ));
            };
            match nv.path.get_ident().map(ToString::to_string).as_deref() {
                Some("description") => {
                    description = Some(expect_str(&nv.value, "description")?.value());
                },
                Some("name") => name = Some(expect_str(&nv.value, "name")?),
                _ => {
                    return Err(syn::Error::new(
                        nv.path.span(),
                        "unknown #[mcp_tool] key (supported: description, name)",
                    ));
                },
            }
        }

        Ok(ToolAttrs { description, name })
    }
}

struct ParamInfo {
    name: Ident,
    /// JSON key: the identifier without any `r#` prefix.
    key: String,
    ty: Type,
    description: Option<String>,
    /// Default value, preserved as a `syn::Expr` so its JSON type (integer,
    /// string, bool, ...) survives into the generated schema and extraction.
    /// Using `Expr` rather than `Lit` also accepts negated literals such as
    /// `#[mcp(default = -1)]`, which parse as a unary expression, not a `Lit`.
    default: Option<Expr>,
    is_optional: bool,
    /// Marked `#[mcp(state)]`: injected from the generated struct's fields
    /// (e.g. a shared store or HTTP client) rather than deserialized from the
    /// JSON arguments. Such params are excluded from the schema.
    is_state: bool,
}

/// How the `Ok` value of the tool function becomes a `ToolResult`.
enum OkKind {
    Text,
    ToolResult,
    Unit,
    Json,
}

fn generate_tool(attrs: ToolAttrs, func: ItemFn) -> syn::Result<TokenStream2> {
    let func_name = &func.sig.ident;

    if !func.sig.generics.params.is_empty() || func.sig.generics.where_clause.is_some() {
        return Err(syn::Error::new(
            func.sig.generics.span(),
            "#[mcp_tool] functions cannot be generic",
        ));
    }

    let tool_name = match &attrs.name {
        Some(lit) => {
            let name = lit.value();
            validate_tool_name(&name).map_err(|msg| syn::Error::new(lit.span(), msg))?;
            name
        },
        None => func_name.unraw().to_string(),
    };
    let tool_struct_name = struct_ident(&tool_name, func_name);

    let doc_attrs: Vec<&Attribute> = func
        .attrs
        .iter()
        .filter(|a| a.path().is_ident("doc"))
        .collect();
    let other_attrs: Vec<&Attribute> = func
        .attrs
        .iter()
        .filter(|a| !a.path().is_ident("doc"))
        .collect();

    let description = match attrs.description {
        Some(d) => d,
        None => doc_text(&func.attrs).ok_or_else(|| {
            syn::Error::new(
                func_name.span(),
                "#[mcp_tool] needs a `description = \"...\"` or a `///` doc comment",
            )
        })?,
    };

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
                quote! { ::core::clone::Clone::clone(&self.#name) }
            } else {
                quote! { #name }
            }
        })
        .collect();

    let func_body = &func.block;
    let output_type = match &func.sig.output {
        ReturnType::Default => {
            return Err(syn::Error::new(
                func.sig.span(),
                "#[mcp_tool] functions must return `Result<T, E>` (E: Display)",
            ));
        },
        ReturnType::Type(_, ty) => ty,
    };

    let convert_ok = match ok_kind(output_type) {
        OkKind::Text => {
            quote! { ::core::result::Result::Ok(::mcp_core::tool::ToolResult::text(result)) }
        },
        OkKind::ToolResult => quote! { ::core::result::Result::Ok(result) },
        OkKind::Unit => quote! {{
            let () = result;
            ::core::result::Result::Ok(::mcp_core::tool::ToolResult::text("OK"))
        }},
        OkKind::Json => quote! { ::mcp_core::tool::ToolResult::json(&result) },
    };

    let struct_doc = if doc_attrs.is_empty() {
        quote! { #[doc = concat!("Generated MCP tool for `", stringify!(#func_name), "`.")] }
    } else {
        quote! { #(#doc_attrs)* }
    };

    // With no state, keep the ergonomic unit struct (`MyTool`); with state,
    // generate a fielded struct plus a `new(...)` constructor.
    let struct_def = if state_params.is_empty() {
        quote! {
            #struct_doc
            pub struct #tool_struct_name;
        }
    } else {
        quote! {
            #struct_doc
            pub struct #tool_struct_name {
                #(#state_names: #state_types,)*
            }

            impl #tool_struct_name {
                #[doc = "Construct the tool with its injected state."]
                #[allow(clippy::too_many_arguments)]
                pub fn new(#(#state_names: #state_types,)*) -> Self {
                    Self { #(#state_names,)* }
                }
            }
        }
    };

    // Point type errors in the body at the user's declared return type.
    let execute_impl_sig = quote_spanned! {output_type.span()=>
        async fn execute_impl(#(#param_names: #param_types,)*) -> #output_type
    };

    Ok(quote! {
        #struct_def

        impl #tool_struct_name {
            #(#other_attrs)*
            #[allow(clippy::too_many_arguments)]
            #execute_impl_sig
            #func_body
        }

        #[::mcp_core::__private::async_trait::async_trait]
        impl ::mcp_core::tool::Tool for #tool_struct_name {
            fn name(&self) -> &str {
                #tool_name
            }

            fn description(&self) -> &str {
                #description
            }

            fn schema(&self) -> ::mcp_core::__private::serde_json::Value {
                #schema
            }

            async fn execute(
                &self,
                args: ::mcp_core::__private::serde_json::Value,
            ) -> ::mcp_core::error::Result<::mcp_core::tool::ToolResult> {
                #arg_extraction

                match Self::execute_impl(#(#call_args,)*).await {
                    ::core::result::Result::Ok(result) => #convert_ok,
                    ::core::result::Result::Err(e) => ::core::result::Result::Ok(
                        ::mcp_core::tool::ToolResult::error(::std::string::ToString::to_string(&e)),
                    ),
                }
            }
        }
    })
}

/// MCP tool-name rule: 1-128 chars from `[A-Za-z0-9_.-]`.
fn validate_tool_name(name: &str) -> Result<(), String> {
    if name.is_empty() || name.len() > 128 {
        return Err("tool name must be 1-128 characters".to_string());
    }
    if let Some(c) = name
        .chars()
        .find(|c| !(c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.')))
    {
        return Err(format!(
            "tool name contains invalid character {c:?} (allowed: A-Z a-z 0-9 _ - .)"
        ));
    }
    Ok(())
}

/// `{PascalCase(name)}Tool`, falling back to the function name when the tool
/// name does not form a valid identifier (e.g. it starts with a digit).
fn struct_ident(tool_name: &str, func_name: &Ident) -> Ident {
    let candidate = format!("{}Tool", to_pascal_case(tool_name));
    syn::parse_str::<Ident>(&candidate)
        .unwrap_or_else(|_| format_ident!("{}Tool", to_pascal_case(&func_name.unraw().to_string())))
}

/// Joined text of `///` doc comments, or `None` if there are none.
fn doc_text(attrs: &[Attribute]) -> Option<String> {
    let lines: Vec<String> = attrs
        .iter()
        .filter(|a| a.path().is_ident("doc"))
        .filter_map(|a| match &a.meta {
            Meta::NameValue(nv) => match &nv.value {
                Expr::Lit(ExprLit {
                    lit: Lit::Str(s), ..
                }) => Some(s.value().trim().to_string()),
                _ => None,
            },
            _ => None,
        })
        .collect();
    let text = lines.join("\n").trim().to_string();
    (!text.is_empty()).then_some(text)
}

fn ok_kind(output: &Type) -> OkKind {
    let Type::Path(tp) = output else {
        return OkKind::Json;
    };
    let Some(seg) = tp.path.segments.last() else {
        return OkKind::Json;
    };
    if seg.ident != "Result" {
        return OkKind::Json;
    }
    let PathArguments::AngleBracketed(args) = &seg.arguments else {
        return OkKind::Json;
    };
    match args.args.first() {
        Some(GenericArgument::Type(Type::Tuple(t))) if t.elems.is_empty() => OkKind::Unit,
        Some(GenericArgument::Type(Type::Path(inner))) => {
            match inner
                .path
                .segments
                .last()
                .map(|s| s.ident.to_string())
                .as_deref()
            {
                Some("String") => OkKind::Text,
                Some("ToolResult") => OkKind::ToolResult,
                _ => OkKind::Json,
            }
        },
        _ => OkKind::Json,
    }
}

fn parse_params(func: &ItemFn) -> syn::Result<Vec<ParamInfo>> {
    let mut params = Vec::new();

    for arg in &func.sig.inputs {
        let pat_type = match arg {
            FnArg::Typed(pat_type) => pat_type,
            FnArg::Receiver(r) => {
                return Err(syn::Error::new(
                    r.span(),
                    "#[mcp_tool] functions cannot take `self`; use #[mcp(state)] parameters for shared state",
                ));
            },
        };
        let Pat::Ident(pat_ident) = &*pat_type.pat else {
            return Err(syn::Error::new(
                pat_type.pat.span(),
                "#[mcp_tool] parameters must be plain identifiers (no destructuring patterns)",
            ));
        };

        let name = pat_ident.ident.clone();
        let ty = (*pat_type.ty).clone();
        let is_optional = is_option_type(&ty);
        let (description, default, is_state) = parse_param_attrs(&pat_type.attrs)?;

        if is_state && (description.is_some() || default.is_some()) {
            return Err(syn::Error::new(
                name.span(),
                "#[mcp(state)] parameters are not part of the schema; remove `description`/`default`",
            ));
        }

        params.push(ParamInfo {
            key: name.unraw().to_string(),
            name,
            ty,
            description,
            default,
            is_optional,
            is_state,
        });
    }

    Ok(params)
}

fn parse_param_attrs(attrs: &[Attribute]) -> syn::Result<(Option<String>, Option<Expr>, bool)> {
    let mut description = None;
    let mut default = None;
    let mut is_state = false;

    for attr in attrs.iter().filter(|a| a.path().is_ident("mcp")) {
        attr.parse_nested_meta(|meta| {
            if meta.path.is_ident("description") {
                let value: LitStr = meta.value()?.parse()?;
                description = Some(value.value());
            } else if meta.path.is_ident("default") {
                // Preserve the expression so the generated `json!(...)` keeps the
                // correct JSON type (e.g. `1` -> integer, not the string "1").
                // Parsing as `Expr` (not `Lit`) also accepts negated literals
                // like `default = -1`, which are unary expressions.
                default = Some(meta.value()?.parse::<Expr>()?);
            } else if meta.path.is_ident("state") {
                // Flag form: `#[mcp(state)]` (no value).
                is_state = true;
            } else {
                return Err(
                    meta.error("unknown #[mcp] key (supported: description, default, state)")
                );
            }
            Ok(())
        })?;
    }

    Ok((description, default, is_state))
}

fn is_option_type(ty: &Type) -> bool {
    if let Type::Path(type_path) = ty
        && let Some(segment) = type_path.path.segments.last()
    {
        return segment.ident == "Option";
    }
    false
}

/// Parameter schema, as JSON, computed at macro-expansion time.
///
/// Unknown (user-defined) types get an unconstrained schema rather than a
/// guessed `"type"`: serde still validates them at call time, and a wrong
/// type hint would mislead the model.
fn type_schema(ty: &Type) -> Map<String, Value> {
    let mut schema = Map::new();
    match ty {
        Type::Reference(r) => return type_schema(&r.elem),
        Type::Paren(p) => return type_schema(&p.elem),
        Type::Group(g) => return type_schema(&g.elem),
        Type::Slice(s) => {
            schema.insert("type".into(), json!("array"));
            schema.insert("items".into(), Value::Object(type_schema(&s.elem)));
        },
        Type::Array(a) => {
            schema.insert("type".into(), json!("array"));
            schema.insert("items".into(), Value::Object(type_schema(&a.elem)));
        },
        Type::Path(tp) => {
            let Some(seg) = tp.path.segments.last() else {
                return schema;
            };
            let generic = |n: usize| -> Option<&Type> {
                let PathArguments::AngleBracketed(args) = &seg.arguments else {
                    return None;
                };
                args.args
                    .iter()
                    .filter_map(|a| match a {
                        GenericArgument::Type(t) => Some(t),
                        _ => None,
                    })
                    .nth(n)
            };
            match seg.ident.to_string().as_str() {
                "String" | "str" | "char" | "PathBuf" | "Path" | "OsString" => {
                    schema.insert("type".into(), json!("string"));
                },
                "i8" | "i16" | "i32" | "i64" | "i128" | "isize" => {
                    schema.insert("type".into(), json!("integer"));
                },
                "u8" | "u16" | "u32" | "u64" | "u128" | "usize" => {
                    schema.insert("type".into(), json!("integer"));
                    schema.insert("minimum".into(), json!(0));
                },
                "f32" | "f64" => {
                    schema.insert("type".into(), json!("number"));
                },
                "bool" => {
                    schema.insert("type".into(), json!("boolean"));
                },
                "Vec" | "VecDeque" | "LinkedList" | "HashSet" | "BTreeSet" | "IndexSet" => {
                    schema.insert("type".into(), json!("array"));
                    if let Some(inner) = generic(0) {
                        schema.insert("items".into(), Value::Object(type_schema(inner)));
                    }
                    if seg.ident.to_string().ends_with("Set") {
                        schema.insert("uniqueItems".into(), json!(true));
                    }
                },
                "HashMap" | "BTreeMap" | "IndexMap" | "Map" => {
                    schema.insert("type".into(), json!("object"));
                    if let Some(value) = generic(1) {
                        let value_schema = type_schema(value);
                        if !value_schema.is_empty() {
                            schema
                                .insert("additionalProperties".into(), Value::Object(value_schema));
                        }
                    }
                },
                "Option" | "Box" | "Arc" | "Rc" | "Cow" => {
                    // `Cow<'_, str>`: the first *type* argument is the payload.
                    if let Some(inner) = generic(0) {
                        return type_schema(inner);
                    }
                },
                // `serde_json::Value` and user-defined types: unconstrained.
                _ => {},
            }
        },
        _ => {},
    }
    schema
}

/// Render a compile-time JSON value as tokens accepted by `serde_json::json!`
/// (string literals are re-quoted by `quote`, so any content is escaped
/// correctly).
fn value_tokens(value: &Value) -> TokenStream2 {
    match value {
        Value::Null => quote! { null },
        Value::Bool(b) => quote! { #b },
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                quote! { #i }
            } else if let Some(u) = n.as_u64() {
                quote! { #u }
            } else {
                let f = n.as_f64().unwrap_or_default();
                quote! { #f }
            }
        },
        Value::String(s) => quote! { #s },
        Value::Array(items) => {
            let items = items.iter().map(value_tokens);
            quote! { [ #(#items),* ] }
        },
        Value::Object(map) => {
            let entries = map.iter().map(|(k, v)| {
                let v = value_tokens(v);
                quote! { #k: #v }
            });
            quote! { { #(#entries),* } }
        },
    }
}

fn generate_schema(params: &[ParamInfo]) -> TokenStream2 {
    let mut inserts = Vec::new();
    let mut required = Vec::new();

    for param in params.iter().filter(|p| !p.is_state) {
        let key = &param.key;
        let mut prop = type_schema(&param.ty);
        if let Some(description) = &param.description {
            prop.insert("description".into(), json!(description));
        }
        let prop_tokens = value_tokens(&Value::Object(prop));

        let default_insert = param.default.as_ref().map(|default| {
            quote! {
                if let ::core::option::Option::Some(obj) = prop.as_object_mut() {
                    obj.insert(
                        ::std::string::String::from("default"),
                        ::mcp_core::__private::serde_json::json!(#default),
                    );
                }
            }
        });

        inserts.push(quote! {
            {
                #[allow(unused_mut)]
                let mut prop = ::mcp_core::__private::serde_json::json!(#prop_tokens);
                #default_insert
                properties.insert(::std::string::String::from(#key), prop);
            }
        });

        if !param.is_optional && param.default.is_none() {
            required.push(key.clone());
        }
    }

    quote! {{
        #[allow(unused_mut)]
        let mut properties = ::mcp_core::__private::serde_json::Map::new();
        #(#inserts)*
        ::mcp_core::__private::serde_json::json!({
            "type": "object",
            "properties": properties,
            "required": [#(#required),*]
        })
    }}
}

fn generate_arg_extraction(params: &[ParamInfo]) -> TokenStream2 {
    let extractions: Vec<_> = params
        .iter()
        .filter(|p| !p.is_state)
        .map(|p| {
            let name = &p.name;
            let ty = &p.ty;
            let key = &p.key;

            // Each parameter is bound to its *declared* type by deserializing the
            // corresponding JSON value via serde. A type mismatch or a missing
            // required parameter becomes a clean `InvalidParameters` error rather
            // than a panic, which is the whole point of the typed macro path.
            // An explicit `null` counts as absent.
            let present = quote! {
                args.get(#key).filter(|v| !v.is_null()).cloned()
            };
            let source = if let Some(default) = &p.default {
                // Checked before `Option`: `#[mcp(default = 10)] x: Option<i32>`
                // yields `Some(10)` when the argument is absent.
                quote! {
                    #present.unwrap_or_else(|| ::mcp_core::__private::serde_json::json!(#default))
                }
            } else if p.is_optional {
                // `Option<T>`: an absent key deserializes from `null` -> `None`.
                quote! {
                    #present.unwrap_or(::mcp_core::__private::serde_json::Value::Null)
                }
            } else {
                quote! {
                    #present.ok_or_else(|| {
                        ::mcp_core::error::MCPError::InvalidParameters(
                            ::std::format!("Missing required parameter: {}", #key)
                        )
                    })?
                }
            };
            quote_spanned! {ty.span()=>
                let #name: #ty = ::mcp_core::__private::serde_json::from_value(#source)
                    .map_err(|e| ::mcp_core::error::MCPError::InvalidParameters(
                        ::std::format!("Invalid parameter '{}': {}", #key, e)
                    ))?;
            }
        })
        .collect();

    quote! {
        #(#extractions)*
    }
}

fn to_pascal_case(s: &str) -> String {
    let mut result = String::new();
    let mut capitalize_next = true;

    for c in s.chars() {
        if !c.is_alphanumeric() {
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

#[cfg(test)]
mod tests {
    use super::*;

    fn ty(s: &str) -> Type {
        syn::parse_str(s).unwrap()
    }

    fn schema(s: &str) -> Value {
        Value::Object(type_schema(&ty(s)))
    }

    #[test]
    fn scalar_schemas() {
        assert_eq!(schema("String"), json!({"type": "string"}));
        assert_eq!(schema("&str"), json!({"type": "string"}));
        assert_eq!(schema("std::path::PathBuf"), json!({"type": "string"}));
        assert_eq!(schema("i64"), json!({"type": "integer"}));
        assert_eq!(schema("u32"), json!({"type": "integer", "minimum": 0}));
        assert_eq!(schema("f32"), json!({"type": "number"}));
        assert_eq!(schema("bool"), json!({"type": "boolean"}));
        assert_eq!(schema("Option<bool>"), json!({"type": "boolean"}));
        assert_eq!(schema("Box<str>"), json!({"type": "string"}));
    }

    #[test]
    fn container_schemas() {
        assert_eq!(
            schema("Vec<String>"),
            json!({"type": "array", "items": {"type": "string"}})
        );
        assert_eq!(
            schema("Option<Vec<u8>>"),
            json!({"type": "array", "items": {"type": "integer", "minimum": 0}})
        );
        assert_eq!(
            schema("HashSet<i32>"),
            json!({"type": "array", "items": {"type": "integer"}, "uniqueItems": true})
        );
        assert_eq!(
            schema("HashMap<String, f64>"),
            json!({"type": "object", "additionalProperties": {"type": "number"}})
        );
        assert_eq!(
            schema("[i8; 3]"),
            json!({"type": "array", "items": {"type": "integer"}})
        );
        assert_eq!(
            schema("Vec<MyThing>"),
            json!({"type": "array", "items": {}})
        );
    }

    #[test]
    fn unknown_types_are_unconstrained() {
        assert_eq!(schema("serde_json::Value"), json!({}));
        assert_eq!(schema("MyEnum"), json!({}));
    }

    #[test]
    fn ok_kinds() {
        assert!(matches!(ok_kind(&ty("Result<String, E>")), OkKind::Text));
        assert!(matches!(
            ok_kind(&ty("anyhow::Result<String>")),
            OkKind::Text
        ));
        assert!(matches!(
            ok_kind(&ty("mcp_core::Result<mcp_core::ToolResult>")),
            OkKind::ToolResult
        ));
        assert!(matches!(ok_kind(&ty("Result<(), E>")), OkKind::Unit));
        assert!(matches!(ok_kind(&ty("Result<Vec<i64>, E>")), OkKind::Json));
        assert!(matches!(ok_kind(&ty("MyAlias<String>")), OkKind::Json));
    }

    #[test]
    fn tool_name_validation() {
        assert!(validate_tool_name("get_user.v2-beta").is_ok());
        assert!(validate_tool_name("").is_err());
        assert!(validate_tool_name("has space").is_err());
        assert!(validate_tool_name(&"a".repeat(129)).is_err());
    }

    #[test]
    fn struct_names() {
        let f: Ident = syn::parse_str("my_fn").unwrap();
        assert_eq!(struct_ident("get.user-v2", &f).to_string(), "GetUserV2Tool");
        assert_eq!(struct_ident("3d_render", &f).to_string(), "MyFnTool");
    }

    #[test]
    fn doc_comment_extraction() {
        let item: ItemFn = syn::parse_str(
            "/// First line.\n/// Second line.\n#[inline]\nasync fn f() -> Result<(), String> { Ok(()) }",
        )
        .unwrap();
        assert_eq!(
            doc_text(&item.attrs).as_deref(),
            Some("First line.\nSecond line.")
        );
    }
}
