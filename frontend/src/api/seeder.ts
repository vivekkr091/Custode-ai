/**
 * Live Demonstration Data Seeder for CUSTODE Showcase.
 * Orchestrates real API calls to populate the Acme Travel AI security control environment:
 * - Agent: Travel Assistant Agent
 * - Tool: Booking Management Tool (booking_tool)
 * - Operations: search_available_rooms, cancel_booking, create_booking
 * - Permissions: explicit allow/deny grants
 * - Policy: High-Value Booking Guardrail (amount > $500 -> require_approval)
 * - Scenario A: Low-risk search -> ALLOW -> Executed
 * - Scenario B: Unauthorized cancel -> BLOCK -> Blocked Execution
 * - Scenario C: High-value hotel reservation ($1,250) -> REQUIRE_APPROVAL -> Pending Approval
 */

import { agentsApi } from './agents';
import { toolsApi } from './tools';
import { permissionsApi } from './permissions';
import { policiesApi } from './policies';
import { runtimeActionsApi } from './runtimeActions';
import { decisionsApi } from './decisions';
import { approvalsApi } from './approvals';
import { executionsApi } from './executions';

export async function seedDemonstrationData(orgId: string, adminUserId?: string): Promise<{ success: boolean; message: string }> {
  try {
    // 1. Create Travel Assistant Agent
    const travelAgent = await agentsApi.create(orgId, {
      name: 'Travel Assistant Agent',
      agent_type: 'assistant',
      environment: 'development',
      description: 'Autonomous customer travel booking assistant for flights, hotels, and itineraries',
    });

    // 2. Create Booking Management Tool
    const bookingTool = await toolsApi.create(orgId, {
      name: 'Booking Management Tool',
      tool_type: 'api',
      environment: 'development',
      description: 'Production booking management API for room availability, reservations, and cancellations',
      endpoint: 'https://api.booking.internal/v1',
    });

    // 3. Create Tool Operations
    const opSearch = await toolsApi.createOperation(orgId, bookingTool.id, {
      name: 'Search Available Rooms',
      operation_type: 'read',
      risk_level: 'low',
      description: 'Query available rooms and rates without booking commitment',
    });

    const opCancel = await toolsApi.createOperation(orgId, bookingTool.id, {
      name: 'Cancel Existing Booking',
      operation_type: 'write',
      risk_level: 'medium',
      description: 'Cancel an existing customer reservation',
    });

    const opCreate = await toolsApi.createOperation(orgId, bookingTool.id, {
      name: 'Create Hotel Booking',
      operation_type: 'write',
      risk_level: 'high',
      description: 'Authorize and commit funds for a hotel reservation',
    });

    // 4. Create Explicit Permissions
    // Allow search_available_rooms
    await permissionsApi.create(orgId, {
      agent_id: travelAgent.id,
      tool_id: bookingTool.id,
      operation_id: opSearch.id,
      environment: 'development',
      effect: 'allow',
    });

    // Deny cancel_booking
    await permissionsApi.create(orgId, {
      agent_id: travelAgent.id,
      tool_id: bookingTool.id,
      operation_id: opCancel.id,
      environment: 'development',
      effect: 'deny',
    });

    // Allow create_booking
    await permissionsApi.create(orgId, {
      agent_id: travelAgent.id,
      tool_id: bookingTool.id,
      operation_id: opCreate.id,
      environment: 'development',
      effect: 'allow',
    });

    // 5. Create High-Value Booking Guardrail Policy and Publish Version
    const bookingPolicy = await policiesApi.create(orgId, {
      name: 'High-Value Booking Guardrail',
      description: 'Mandates human security authorization for hotel bookings exceeding $500',
      enforcement_mode: 'enforce',
    });

    const v1 = await policiesApi.createVersion(orgId, bookingPolicy.id, {
      rules: [
        {
          name: 'Require Approval for Bookings > $500',
          effect: 'require_approval',
          conditions: [
            { field: 'action.amount', operator: 'gt', value: 500 },
          ],
        },
      ],
    });
    await policiesApi.publishVersion(orgId, bookingPolicy.id, v1.id);

    // 6. Create Runtime Actions & Execute Scenarios

    // Scenario A: Low-risk Room Search -> ALLOW -> Execute directly
    const actionA = await runtimeActionsApi.create(orgId, travelAgent.id, {
      tool_id: bookingTool.id,
      operation_id: opSearch.id,
      environment: 'dev',
      action_type: 'search_rooms',
      resource: '/destinations/paris/rooms',
      resource_type: 'hotel_inventory',
      parameters: { city: 'Paris', check_in: '2026-11-01', check_out: '2026-11-05', guests: 2 },
    });
    await decisionsApi.decide(orgId, actionA.id);
    await executionsApi.execute(orgId, actionA.id);

    // Scenario B: Unauthorized Cancellation -> BLOCK -> Execution Blocked by Guard
    const actionB = await runtimeActionsApi.create(orgId, travelAgent.id, {
      tool_id: bookingTool.id,
      operation_id: opCancel.id,
      environment: 'dev',
      action_type: 'cancel_reservation',
      resource: '/reservations/RES-448291',
      resource_type: 'customer_reservation',
      parameters: { reservation_id: 'RES-448291', reason: 'unauthorized_customer_request' },
    });
    await decisionsApi.decide(orgId, actionB.id);
    await executionsApi.execute(orgId, actionB.id);

    // Scenario C: High-Value Booking ($1,250) -> REQUIRE_APPROVAL -> Create Approval Request (Pending in Inbox)
    const actionC = await runtimeActionsApi.create(orgId, travelAgent.id, {
      tool_id: bookingTool.id,
      operation_id: opCreate.id,
      environment: 'dev',
      action_type: 'book_hotel',
      amount: 1250,
      currency: 'USD',
      resource: '/bookings/hotel_resort_78',
      resource_type: 'financial_reservation',
      parameters: { hotel_id: 'HTL-771', room_type: 'penthouse_suite', nights: 3, amount: 1250, currency: 'USD' },
    });
    const decC = await decisionsApi.decide(orgId, actionC.id);
    const apprC = await approvalsApi.create(orgId, actionC.id, {
      decision_id: decC.id,
      reason: 'High-value hotel reservation commitment of $1,250.00 requires authorized human review.',
    });

    if (adminUserId && false) {
      // Intentionally keep pending for live presentation
      await approvalsApi.approve(orgId, apprC.id, adminUserId, {
        reviewer_note: 'Executive travel itinerary authorized.',
      });
      await executionsApi.execute(orgId, actionC.id);
    }

    return {
      success: true,
      message: 'Successfully seeded Acme Travel AI agents, tools, permissions, policies, actions, decisions, and approval inbox!',
    };
  } catch (err: any) {
    return {
      success: false,
      message: err.message || 'Failed to seed demonstration data.',
    };
  }
}

export const seedSampleScenario = seedDemonstrationData;
