// Single API scope per AUTH-03. msalConfig + every acquireToken*({scopes}) use this array.
//
// VITE_API_AUDIENCE may or may not already include the `api://` prefix depending on how
// `infra/external/` outputs are formatted; the planner left this open ("api://${VITE_API_AUDIENCE_RAW}/access_as_user"
// or "${VITE_API_AUDIENCE}/access_as_user"). We accept either shape — if the env var
// already starts with `api://` we append the scope name; otherwise we prepend `api://`.
const audience = import.meta.env.VITE_API_AUDIENCE
const normalized = audience.startsWith('api://') ? audience : `api://${audience}`

export const API_SCOPE = `${normalized}/access_as_user`

export const loginRequest = {
  scopes: [API_SCOPE],
}
