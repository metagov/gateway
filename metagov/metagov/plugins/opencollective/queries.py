logged_in_account = """
query loggedInAccount {
 loggedInAccount {
   id
   name
   slug
 }
}
"""

collective = """
query Collective($slug: String) {
    collective(id: null, slug: $slug, githubHandle: null, throwIfMissing: null) {
        id
        legacyId
        name
    }
}
"""

expense = """
query Expense($reference: ExpenseReferenceInput) {
    expense(id: null, expense: $reference, draftKey: "test") {
        id
        createdAt
        description
        longDescription
        amount
        currency
        legacyId
        type
        status
        createdByAccount {
          isAdmin
          name
          slug
        }
        tags
    }
}
"""

members = """
query Collective($slug: String) {
    collective(id: null, slug: $slug, githubHandle: null, throwIfMissing: null) {
        id
        name
        members(limit: 10) {
            totalCount
            nodes {
                id
                account {
                    name
                    slug
                }
            }
        }
    }
}
"""


create_conversation = """
mutation CreateConversation($title: String!, $html: String!, $CollectiveId: String!, $tags: [String]) {
  createConversation(title: $title, html: $html, CollectiveId: $CollectiveId, tags: $tags) {
    id
    slug
    title
    summary
    tags
    createdAt
    __typename
  }
}
"""

create_comment = """
mutation CreateComment($comment: CommentCreateInput!) {
  createComment(comment: $comment) {
    ...CommentFields
    __typename
  }
}

fragment CommentFields on Comment {
  id
  createdAt
  html
  reactions
  userReactions
  __typename
}
"""
