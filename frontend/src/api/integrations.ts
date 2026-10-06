import { api } from './apiClient';
import {
  Integration,
  IntegrationCreate,
  IntegrationCreateResponse,
  SupportedEventsResponse,
  WebhookDelivery,
  PaginatedResponse,
} from '../types';

export const integrationsApi = {
  list: (
    organizationId: string,
    params?: { status?: string; limit?: number; offset?: number }
  ) =>
    api.get<PaginatedResponse<Integration>>(
      `/api/v1/organizations/${organizationId}/integrations`,
      { params }
    ),

  get: (organizationId: string, integrationId: string) =>
    api.get<Integration>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}`
    ),

  create: (organizationId: string, data: IntegrationCreate) =>
    api.post<IntegrationCreateResponse>(
      `/api/v1/organizations/${organizationId}/integrations`,
      data
    ),

  update: (
    organizationId: string,
    integrationId: string,
    data: Partial<IntegrationCreate>
  ) =>
    api.patch<Integration>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}`,
      data
    ),

  suspend: (organizationId: string, integrationId: string) =>
    api.post<Integration>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}/suspend`
    ),

  revoke: (organizationId: string, integrationId: string) =>
    api.post<Integration>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}/revoke`
    ),

  testPing: (organizationId: string, integrationId: string) =>
    api.post<WebhookDelivery>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}/test`
    ),

  listDeliveries: (
    organizationId: string,
    integrationId: string,
    params?: { status?: string; event_type?: string; limit?: number; offset?: number }
  ) =>
    api.get<PaginatedResponse<WebhookDelivery>>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}/deliveries`,
      { params }
    ),

  getDelivery: (
    organizationId: string,
    integrationId: string,
    deliveryId: string
  ) =>
    api.get<WebhookDelivery>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}/deliveries/${deliveryId}`
    ),

  retryDelivery: (
    organizationId: string,
    integrationId: string,
    deliveryId: string
  ) =>
    api.post<WebhookDelivery>(
      `/api/v1/organizations/${organizationId}/integrations/${integrationId}/deliveries/${deliveryId}/retry`
    ),

  getSupportedEvents: (organizationId: string) =>
    api.get<SupportedEventsResponse>(
      `/api/v1/organizations/${organizationId}/integrations/supported-events`
    ),
};
