import type { ErrorCode } from './schema';

interface ErrorPresentation {
  title: string;
  hint: string;
}

export const errorPresentations: Record<ErrorCode, ErrorPresentation> = {
  INVALID_ARGUMENT: { title: 'Check the submitted details', hint: 'Correct the highlighted value and try again.' },
  INVALID_TYPE: { title: 'Unsupported catalog configuration', hint: 'Choose a supported catalog type.' },
  METHOD_NOT_ALLOWED: { title: 'Unsupported request', hint: 'Refresh the page and try again.' },
  NOT_FOUND: { title: 'Resource not found', hint: 'It may have been removed or is no longer available.' },
  ALREADY_EXISTS: { title: 'Catalog name already exists', hint: 'Choose a unique catalog name.' },
  UNAUTHENTICATED: { title: 'Authentication required', hint: 'Sign in again and retry.' },
  PERMISSION_DENIED: { title: 'Permission denied', hint: 'Verify your credentials have the required access.' },
  CONNECTION_FAILED: { title: 'Could not connect', hint: 'Check the endpoint, credentials, and warehouse.' },
  CONNECTION_TIMEOUT: { title: 'Connection timed out', hint: 'Check the endpoint is reachable and try again.' },
  UNAVAILABLE: { title: 'Service temporarily unavailable', hint: 'Wait a moment and try again.' },
  KEYRING: { title: 'Could not store credentials', hint: 'Check the system credential store and try again.' },
  JSON: { title: 'Invalid service response', hint: 'Try again or contact support if it persists.' },
  INFERENCE_FAILED: { title: 'The agent could not run', hint: 'Try again in a moment.' },
  RATE_LIMITED: { title: 'Rate limit reached', hint: 'Wait before trying again.' },
  MODEL_NOT_FOUND: { title: 'Configured model is unavailable', hint: 'Check the model configuration.' },
  INTERNAL: { title: 'Something went wrong', hint: 'Try again in a moment.' },
};

export function presentError(code?: ErrorCode | null): ErrorPresentation {
  return code ? errorPresentations[code] : errorPresentations.INTERNAL;
}
