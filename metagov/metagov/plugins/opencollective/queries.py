expenseFields = """
fragment expenseFields on Expense {
    id
    legacyId
    description
    longDescription
    amount
    createdAt
    currency
    type
    status
    account {
      id
      legacyId
      slug
    }
    payee {
      id
      legacyId
      slug
    }
    createdByAccount {
      id
      legacyId
      slug
    }
    requestedByAccount {
      id
      legacyId
      slug
    }
    activities {
      id,
      type,
      createdAt,
      data,
      individual {
        id,
        slug
      }
    }
    items {
      id
      amount
      createdAt
      updatedAt
      incurredAt
      description
      url
    }
    tags
}
"""

conversationFields = """
fragment conversationFields on Conversation {
  id
  slug
  title
  createdAt
  updatedAt
  tags
  summary
  body {
      id
      reactions
  }
  stats {
      commentsCount
  }
}
"""


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
        type
        childrenAccounts(limit: 50, offset: 0) {
            totalCount
            nodes {
                id
                legacyId
                slug
                name
                type
            }
        }
    }
}
"""

expense = (
    """
query Expense($reference: ExpenseReferenceInput) {
    expense(id: null, expense: $reference, draftKey: "test") {
        ...expenseFields
    }
}
%s"""
    % expenseFields
)

members = """
query Collective($slug: String) {
    collective(id: null, slug: $slug, githubHandle: null, throwIfMissing: null) {
        id
        name
        members(limit: 10) {
            totalCount
            nodes {
                id
                role
                tier {
                  id
                  slug
                  name
                  description
                  type
                  frequency
                }
                createdAt
                updatedAt
                since
                totalDonations {
                  value
                  currency
                }
                account {
                    id
                    slug
                    name
                    twitterHandle
                    githubHandle
                    isArchived
                    isActive
                    isHost
                    isAdmin
                }
            }
        }
    }
}
"""

conversation = (
    """
query Conversation($id: String!) {
    conversation(id: $id) {
        ...conversationFields
    }
}
%s"""
    % conversationFields
)


create_conversation = (
    """
mutation CreateConversation($title: String!, $html: String!, $CollectiveId: String!, $tags: [String]) {
  createConversation(title: $title, html: $html, CollectiveId: $CollectiveId, tags: $tags) {
    ...conversationFields
  }
}
%s"""
    % conversationFields
)

edit_conversation = (
    """
mutation EditConverstaion($id: String!, $title: String!, $tags: [String]) {
  editConversation(id: $id, title: $title, tags: $tags) {
    ...conversationFields
  }
}
%s"""
    % conversationFields
)

create_comment = """
mutation CreateComment($comment: CommentCreateInput!) {
  createComment(comment: $comment) {
    ...commentFields
  }
}

fragment commentFields on Comment {
  id
  createdAt
  html
  reactions
}
"""

process_expense = (
    """
mutation ProcessExpense(
    $reference: ExpenseReferenceInput!,
    $action: ExpenseProcessAction!
) {
  processExpense(expense: $reference, action: $action, paymentParams: null) {
    ...expenseFields
  }
}
%s"""
    % expenseFields
)
