import { useState } from 'react';

const DEFAULT_OPEN_DEPTH = 2;
const SMALLEST_TABLE_ROWS = 2;

/** Props for JsonView. */
interface JsonViewProps {
  value: unknown;
  name?: string;
  depth?: number;
}

/**
 * Shows a JSON value as a tree whose branches can be folded away.
 *
 * An array of similar objects is offered as a table instead, because a holdings or positions list
 * is far easier to read in rows than as a hundred numbered branches.
 * @param props The value to show, the name it sits under and how deep it is.
 * @returns The tree.
 */
export function JsonView(props: JsonViewProps) {
  const { value, name, depth = 0 } = props;

  if (value === null) {
    return <Leaf name={name} text="null" className="json-null" />;
  }
  if (typeof value === 'boolean') {
    return <Leaf name={name} text={value ? 'true' : 'false'} className="json-boolean" />;
  }
  if (typeof value === 'number') {
    return <Leaf name={name} text={String(value)} className="json-number" />;
  }
  if (typeof value === 'string') {
    return <Leaf name={name} text={value} className="json-string" />;
  }
  if (Array.isArray(value)) {
    return <ArrayNode values={value} name={name} depth={depth} />;
  }
  if (typeof value === 'object') {
    return <ObjectNode entries={Object.entries(value as Record<string, unknown>)} name={name} depth={depth} />;
  }
  return <Leaf name={name} text={String(value)} className="json-string" />;
}

/** Props for Leaf. */
interface LeafProps {
  name?: string;
  text: string;
  className: string;
}

/**
 * One value that has nothing inside it.
 * @param props The name, the text to show and the class that colours it.
 * @returns The line.
 */
function Leaf(props: LeafProps) {
  const { name, text, className } = props;
  return (
    <div className="json-line">
      {name === undefined ? null : <span className="json-key">{name}</span>}
      <span className={className}>{text === '' ? '(empty)' : text}</span>
    </div>
  );
}

/** Props for ObjectNode. */
interface ObjectNodeProps {
  entries: Array<[string, unknown]>;
  name?: string;
  depth: number;
}

/**
 * An object, shown as a foldable list of its fields.
 * @param props The fields, the name the object sits under and how deep it is.
 * @returns The branch.
 */
function ObjectNode(props: ObjectNodeProps) {
  const { entries, name, depth } = props;
  if (entries.length === 0) {
    return <Leaf name={name} text="{}" className="json-empty" />;
  }
  return (
    <details className="json-branch" open={depth < DEFAULT_OPEN_DEPTH}>
      <summary>
        {name === undefined ? <span className="json-key">object</span> : <span className="json-key">{name}</span>}
        <span className="json-count">
          {entries.length} {entries.length === 1 ? 'field' : 'fields'}
        </span>
      </summary>
      <div className="json-children">
        {entries.map(([key, child]) => (
          <JsonView key={key} value={child} name={key} depth={depth + 1} />
        ))}
      </div>
    </details>
  );
}

/** Props for ArrayNode. */
interface ArrayNodeProps {
  values: unknown[];
  name?: string;
  depth: number;
}

/**
 * An array, shown as a foldable list, or as a table when its items are alike.
 * @param props The items, the name the array sits under and how deep it is.
 * @returns The branch.
 */
function ArrayNode(props: ArrayNodeProps) {
  const { values, name, depth } = props;
  const columns = tableColumns(values);
  const [asTable, setAsTable] = useState(columns !== null);

  if (values.length === 0) {
    return <Leaf name={name} text="[]" className="json-empty" />;
  }
  return (
    <details className="json-branch" open={depth < DEFAULT_OPEN_DEPTH}>
      <summary>
        {name === undefined ? <span className="json-key">list</span> : <span className="json-key">{name}</span>}
        <span className="json-count">
          {values.length} {values.length === 1 ? 'item' : 'items'}
        </span>
        {columns === null ? null : (
          <button
            type="button"
            className="button button-quiet json-toggle"
            onClick={(event) => {
              event.preventDefault();
              setAsTable(!asTable);
            }}
          >
            {asTable ? 'Show as tree' : 'Show as table'}
          </button>
        )}
      </summary>
      {columns !== null && asTable ? (
        <ObjectTable values={values as Array<Record<string, unknown>>} columns={columns} />
      ) : (
        <div className="json-children">
          {values.map((child, index) => (
            <JsonView key={index} value={child} name={String(index)} depth={depth + 1} />
          ))}
        </div>
      )}
    </details>
  );
}

/** Props for ObjectTable. */
interface ObjectTableProps {
  values: Array<Record<string, unknown>>;
  columns: string[];
}

/**
 * A list of similar objects, one row each.
 * @param props The objects and the columns they share.
 * @returns The table.
 */
function ObjectTable(props: ObjectTableProps) {
  const { values, columns } = props;
  return (
    <div className="table-scroll json-table">
      <table className="data-table compact">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {values.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column} className={typeof row[column] === 'number' ? 'numeric' : undefined}>
                  {cellText(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Decides whether a list is a list of alike objects, and what its columns would be.
 *
 * Every item must be a plain object, and every item must have the same field names, because a
 * table that silently dropped a field present on only some rows would be misleading.
 * @param values The list to judge.
 * @returns The shared field names, or null when the list is not a table.
 */
function tableColumns(values: unknown[]): string[] | null {
  if (values.length < SMALLEST_TABLE_ROWS) {
    return null;
  }
  let columns: string[] | null = null;
  for (const value of values) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      return null;
    }
    const names = Object.keys(value as Record<string, unknown>);
    if (names.length === 0) {
      return null;
    }
    if (columns === null) {
      columns = names;
    } else if (columns.length !== names.length || !names.every((name) => columns?.includes(name))) {
      return null;
    }
  }
  return columns;
}

/**
 * The text one table cell shows.
 * @param value Whatever the field held.
 * @returns A short readable rendering, with nested values shown as JSON.
 */
function cellText(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}
