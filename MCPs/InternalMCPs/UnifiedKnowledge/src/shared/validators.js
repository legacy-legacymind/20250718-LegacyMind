import { z } from 'zod';

// Enums
export const TicketStatus = z.enum(['OPEN', 'IN_PROGRESS', 'BLOCKED', 'REVIEW', 'TESTING', 'CLOSED', 'CANCELLED']);
export const TicketPriority = z.enum(['low', 'medium', 'high', 'urgent']);
export const TicketType = z.enum(['bug', 'feature', 'question', 'task', 'improvement']);
export const LinkType = z.enum(['blocks', 'blocked_by', 'relates_to', 'duplicates', 'parent', 'child']);

// Base schemas
const TicketIdSchema = z.string().min(1).max(255);
const TitleSchema = z.string().min(1).max(500);
const DescriptionSchema = z.string().max(5000).optional();
const TagSchema = z.string().min(1).max(50);
const TagsSchema = z.array(TagSchema).max(10).optional();
const AssigneeSchema = z.string().min(1).max(255);
const MemberSchema = z.string().min(1).max(255);

// Ticket creation schema
export const createTicketSchema = z.object({
  title: TitleSchema,
  description: DescriptionSchema,
  priority: TicketPriority.default('medium'),
  type: TicketType.default('task'),
  tags: TagsSchema,
  assignee: AssigneeSchema.optional(),
  metadata: z.record(z.any()).optional()
});

// Ticket update schema
export const updateTicketSchema = z.object({
  ticket_id: TicketIdSchema,
  updates: z.object({
    title: TitleSchema.optional(),
    description: DescriptionSchema,
    status: TicketStatus.optional(),
    priority: TicketPriority.optional(),
    type: TicketType.optional(),
    tags: TagsSchema,
    assignee: AssigneeSchema.optional(),
    metadata: z.record(z.any()).optional()
  }).refine(data => Object.keys(data).length > 0, {
    message: "At least one field must be provided for update"
  })
});

// Search tickets schema
export const searchTicketsSchema = z.object({
  query: z.string().optional(),
  filters: z.object({
    status: z.union([TicketStatus, z.array(TicketStatus)]).optional(),
    priority: z.union([TicketPriority, z.array(TicketPriority)]).optional(),
    type: z.union([TicketType, z.array(TicketType)]).optional(),
    assignee: z.union([AssigneeSchema, z.array(AssigneeSchema)]).optional(),
    tags: z.union([TagSchema, z.array(TagSchema)]).optional(),
    created_after: z.string().datetime().optional(),
    created_before: z.string().datetime().optional(),
    updated_after: z.string().datetime().optional(),
    updated_before: z.string().datetime().optional()
  }).optional(),
  sort_by: z.enum(['created_at', 'updated_at', 'priority', 'status']).optional(),
  sort_order: z.enum(['asc', 'desc']).optional(),
  limit: z.number().int().min(1).max(100).optional(),
  offset: z.number().int().min(0).optional()
});

// List tickets schema
export const listTicketsSchema = z.object({
  status: z.union([TicketStatus, z.array(TicketStatus)]).optional(),
  assignee: AssigneeSchema.optional(),
  priority: z.union([TicketPriority, z.array(TicketPriority)]).optional(),
  type: z.union([TicketType, z.array(TicketType)]).optional(),
  tags: z.union([TagSchema, z.array(TagSchema)]).optional(),
  sort_by: z.enum(['created_at', 'updated_at', 'priority', 'status']).optional(),
  sort_order: z.enum(['asc', 'desc']).optional(),
  limit: z.number().int().min(1).max(100).optional(),
  offset: z.number().int().min(0).optional()
});

// Get ticket schema
export const getTicketSchema = z.object({
  ticket_id: TicketIdSchema,
  include_history: z.boolean().optional(),
  include_comments: z.boolean().optional(),
  include_links: z.boolean().optional()
});

// Close ticket schema
export const closeTicketSchema = z.object({
  ticket_id: TicketIdSchema,
  resolution: z.string().min(1).max(1000),
  metadata: z.record(z.any()).optional()
});

// Assign ticket schema
export const assignTicketSchema = z.object({
  ticket_id: TicketIdSchema,
  assignee: AssigneeSchema,
  notify: z.boolean().optional()
});

// Add member schema
export const addMemberSchema = z.object({
  ticket_id: TicketIdSchema,
  member: MemberSchema,
  role: z.enum(['viewer', 'contributor', 'owner']).optional(),
  notify: z.boolean().optional()
});

// Link tickets schema
export const linkTicketsSchema = z.object({
  source_ticket_id: TicketIdSchema,
  target_ticket_id: TicketIdSchema,
  link_type: LinkType,
  metadata: z.record(z.any()).optional()
});

// Response schemas
export const ticketResponseSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  status: TicketStatus,
  priority: TicketPriority,
  type: TicketType,
  tags: z.array(z.string()),
  assignee: z.string().nullable(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  closed_at: z.string().datetime().nullable(),
  resolution: z.string().nullable(),
  metadata: z.record(z.any())
});

export const ticketListResponseSchema = z.object({
  tickets: z.array(ticketResponseSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int()
});

export const linkResponseSchema = z.object({
  id: z.string(),
  source_ticket_id: z.string(),
  target_ticket_id: z.string(),
  link_type: LinkType,
  created_at: z.string().datetime(),
  metadata: z.record(z.any())
});

// Error response schema
export const errorResponseSchema = z.object({
  error: z.string(),
  code: z.string().optional(),
  details: z.record(z.any()).optional()
});

// Validation helper functions
export function validateCreateTicket(data) {
  return createTicketSchema.safeParse(data);
}

export function validateUpdateTicket(data) {
  return updateTicketSchema.safeParse(data);
}

export function validateSearchTickets(data) {
  return searchTicketsSchema.safeParse(data);
}

export function validateListTickets(data) {
  return listTicketsSchema.safeParse(data);
}

export function validateGetTicket(data) {
  return getTicketSchema.safeParse(data);
}

export function validateCloseTicket(data) {
  return closeTicketSchema.safeParse(data);
}

export function validateAssignTicket(data) {
  return assignTicketSchema.safeParse(data);
}

export function validateAddMember(data) {
  return addMemberSchema.safeParse(data);
}

export function validateLinkTickets(data) {
  return linkTicketsSchema.safeParse(data);
}