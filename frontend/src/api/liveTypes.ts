/** One tab the live view offers, as the server's catalogue declares it. */
export interface LiveView {
  name: string;
  label: string;
  kind: 'document' | 'hash_field' | 'hash_documents' | 'table';
  note: string;
  needs_broker: boolean;
}

/** One query parameter a UBI endpoint accepts. */
export interface ApiParameter {
  name: string;
  required: boolean;
  example: string;
  note: string;
}

/** One GET endpoint of UBI's REST API that the live view may call. */
export interface ApiEndpoint {
  name: string;
  group: string;
  label: string;
  path: string;
  note: string;
  authenticated: boolean;
  parameters: ApiParameter[];
}

/** Everything the live view needs before it can show anything. */
export interface LiveCatalogue {
  brokers: string[];
  broker_views: LiveView[];
  unified_views: LiveView[];
  api_endpoints: ApiEndpoint[];
  mapping_date: string | null;
}

/** One Redis string key or hash field, read as it stands. */
export interface LiveDocument {
  key: string;
  field?: string;
  kind: string;
  exists: boolean;
  byte_size: number;
  expires_in_seconds: number | null;
  document: unknown;
  text: string | null;
}

/** One field of a hash whose every field holds its own document. */
export interface LiveHashEntry {
  field: string;
  document: unknown;
  text: string | null;
}

/** A whole hash of JSON documents, such as a broker's order book. */
export interface LiveHashDocuments {
  key: string;
  exists: boolean;
  field_count: number;
  expires_in_seconds: number | null;
  polled_at: string | null;
  entries: LiveHashEntry[];
}

/** One row of a table, as its key and its cells in column order. */
export interface LiveTableRow {
  key: string;
  values: unknown[];
}

/** One page of a table, or the matches a search found. */
export interface LiveTablePage {
  key: string;
  exists: boolean;
  key_column: string;
  columns: string[];
  field_prefix: string | null;
  total_fields: number;
  rows: LiveTableRow[];
  cursor: string | null;
  scanned_fields: number;
  search: string | null;
  complete: boolean;
}

/** A tab and whatever its reader returned. */
export interface LiveViewAnswer<Value> {
  scope: string;
  name: string;
  label: string;
  kind: string;
  note: string;
  broker: string | null;
  value: Value;
}

/** One health reading from a data store, with the container it runs in. */
export interface StoreHealth {
  name: string;
  label: string;
  online: boolean;
  error: string | null;
  response_milliseconds: number | null;
  version: string | null;
  started_at: number | null;
  uptime_seconds: number | null;
  parameters: Array<{ group: string; name: string; value: unknown }>;
  container: {
    name: string;
    state: string;
    started_at: number | null;
    restart_count: number | null;
    health: string | null;
  } | null;
}

/** All three stores read together. */
export interface DatabaseHealth {
  read_at: number;
  docker_error: string | null;
  stores: StoreHealth[];
}

/** What one call to a UBI endpoint returned. */
export interface ApiCallResult {
  endpoint: string;
  url: string;
  status_code: number | null;
  elapsed_milliseconds: number;
  byte_size: number;
  truncated: boolean;
  document: unknown;
  text: string | null;
  token_used: boolean;
  error: string | null;
}
