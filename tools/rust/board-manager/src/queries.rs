//! GraphQL documents used by the board manager.
//!
//! All dynamic values are passed as variables; no user input is interpolated
//! into query text (the one exception, batched approval checks, only
//! interpolates integer issue numbers - see `approval::batch_query`).

/// Field values of a project item (single select, text and number).
macro_rules! item_field_values_fragment {
    () => {
        "
fragment ItemFieldValues on ProjectV2Item {
  fieldValues(first: 30) {
    nodes {
      ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
      ... on ProjectV2ItemFieldTextValue { text field { ... on ProjectV2FieldCommon { name } } }
      ... on ProjectV2ItemFieldNumberValue { number field { ... on ProjectV2FieldCommon { name } } }
    }
  }
}
"
    };
}

/// Issue content fields used to build [`crate::models::Issue`].
macro_rules! issue_content_fragment {
    () => {
        "
fragment IssueContent on Issue {
  number
  title
  body
  state
  createdAt
  updatedAt
  url
  labels(first: 30) { nodes { name } }
}
"
    };
}

/// Resolve a project (user- or org-owned) with all field definitions.
pub const PROJECT: &str = r#"
query Project($owner: String!, $number: Int!) {
  user(login: $owner) { projectV2(number: $number) { ...ProjectMeta } }
  organization(login: $owner) { projectV2(number: $number) { ...ProjectMeta } }
}
fragment ProjectMeta on ProjectV2 {
  id
  title
  fields(first: 100) {
    nodes {
      ... on ProjectV2FieldCommon { id name dataType }
      ... on ProjectV2SingleSelectField { options { id name } }
    }
  }
}
"#;

/// One page of board items with field values and issue content.
pub const BOARD_ITEMS: &str = concat!(
    r#"
query BoardItems($projectId: ID!, $cursor: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          ...ItemFieldValues
          content { ...IssueContent }
        }
      }
    }
  }
}
"#,
    item_field_values_fragment!(),
    issue_content_fragment!()
);

/// One page of board items with only issue numbers (cheap membership scan).
pub const BOARD_NUMBERS: &str = r#"
query BoardNumbers($projectId: ID!, $cursor: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { content { ... on Issue { number } } }
      }
    }
  }
}
"#;

/// Look up one issue and its project items directly (no board scan).
pub const ISSUE_ITEM: &str = concat!(
    r#"
query IssueItem($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      id
      ...IssueContent
      projectItems(first: 50, includeArchived: false) {
        nodes {
          id
          project { id }
          ...ItemFieldValues
        }
      }
    }
  }
}
"#,
    item_field_values_fragment!(),
    issue_content_fragment!()
);

/// Most recent comments of an issue (for claim reconstruction).
pub const CLAIM_COMMENTS: &str = r#"
query ClaimComments($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      comments(last: 100) { nodes { body createdAt author { __typename login } } }
    }
  }
}
"#;

/// A page of issue comments with authors (approval continuation).
pub const COMMENT_PAGE: &str = r#"
query CommentPage($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      comments(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { body author { __typename login } }
      }
    }
  }
}
"#;

/// Post a comment.
pub const ADD_COMMENT: &str = r#"
mutation AddComment($subjectId: ID!, $body: String!) {
  addComment(input: {subjectId: $subjectId, body: $body}) { commentEdge { node { id } } }
}
"#;

/// Set a project item field value.
pub const UPDATE_FIELD: &str = r#"
mutation UpdateField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
  updateProjectV2ItemFieldValue(
    input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
  ) { projectV2Item { id } }
}
"#;

/// Clear a project item field value.
pub const CLEAR_FIELD: &str = r#"
mutation ClearField($projectId: ID!, $itemId: ID!, $fieldId: ID!) {
  clearProjectV2ItemFieldValue(
    input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId}
  ) { projectV2Item { id } }
}
"#;

/// Add an issue to the project (idempotent on GitHub's side).
pub const ADD_ITEM: &str = r#"
mutation AddItem($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemByContentId(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
"#;

#[cfg(test)]
mod tests {
    use super::*;

    /// Every fragment spread must have a matching definition and vice versa,
    /// otherwise GitHub rejects the document.
    #[test]
    fn fragments_are_defined_and_used() {
        for doc in [PROJECT, BOARD_ITEMS, ISSUE_ITEM] {
            for name in ["ProjectMeta", "ItemFieldValues", "IssueContent"] {
                let spread = doc.contains(&format!("...{name}"));
                let defined = doc.contains(&format!("fragment {name} on"));
                assert_eq!(spread, defined, "fragment {name} mismatch");
            }
        }
    }

    #[test]
    fn braces_balanced() {
        for doc in [
            PROJECT,
            BOARD_ITEMS,
            BOARD_NUMBERS,
            ISSUE_ITEM,
            CLAIM_COMMENTS,
            COMMENT_PAGE,
            ADD_COMMENT,
            UPDATE_FIELD,
            CLEAR_FIELD,
            ADD_ITEM,
        ] {
            let open = doc.matches('{').count();
            let close = doc.matches('}').count();
            assert_eq!(open, close, "unbalanced braces in:\n{doc}");
        }
    }
}
