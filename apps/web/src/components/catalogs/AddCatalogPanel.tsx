import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { XIcon } from 'lucide-react';
import type { CatalogCreateRequest, CatalogType, ErrorCode, SqlDatabaseType } from '../../api/types';
import { ApiError } from '../../api/client';
import { presentError } from '../../api/errors';
import { useLakeGen } from '../../state/LakeGenContext';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { Field } from '../ui/Field';
import { IconButton } from '../ui/IconButton';
import { Select } from '../ui/Select';
import { useToast } from '../ui/Toast';
import { ConnectStatusDialog, type ConnectStatus } from './ConnectStatusDialog';

const CONNECTION_TIMEOUT_MS = 30_000;

const typeOptions: { value: CatalogType; title: string; description: string }[] = [
  { value: 'glue', title: 'Glue', description: 'AWS Glue Data Catalog' },
  { value: 'rest', title: 'REST', description: 'Iceberg REST catalog' },
  { value: 'sql', title: 'SQL', description: 'JDBC-backed catalog' },
];

type SqlNetworkDatabaseType = Exclude<SqlDatabaseType, 'sqlite'>;

const SQL_DEFAULT_PORT: Record<SqlNetworkDatabaseType, number> = {
  postgresql: 5432,
  mysql: 3306,
};

interface AddCatalogPanelProps {
  open: boolean;
  onClose: () => void;
}

function omitEmpty(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function parsePort(raw: string, fallback: number): number | undefined {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return fallback;
  const n = Number(trimmed);
  if (!Number.isInteger(n) || n < 1 || n > 65535) return undefined;
  return n;
}

export function AddCatalogPanel({ open, onClose }: AddCatalogPanelProps) {
  const { addCatalog, catalogs, refreshCatalogs } = useLakeGen();
  const { notify } = useToast();
  const [type, setType] = useState<CatalogType>('glue');
  const [name, setName] = useState('');
  const [warehouse, setWarehouse] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<ErrorCode | null>(null);
  const [connectStatus, setConnectStatus] = useState<ConnectStatus | null>(null);
  const connectAbortRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  const [region, setRegion] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');

  const [glueId, setGlueId] = useState('');

  const [uri, setUri] = useState('');
  const [token, setToken] = useState('');
  const [credential, setCredential] = useState('');
  const [oauth2Uri, setOauth2Uri] = useState('');
  const [restAuthType, setRestAuthType] = useState('');
  const [scope, setScope] = useState('');
  const [signingName, setSigningName] = useState('');
  const [signingRegion, setSigningRegion] = useState('');
  const [signingV4, setSigningV4] = useState(true);
  const [noIdentifierFields, setNoIdentifierFields] = useState(false);

  const [databaseType, setDatabaseType] = useState<SqlNetworkDatabaseType>('postgresql');
  const [host, setHost] = useState('');
  const [port, setPort] = useState(String(SQL_DEFAULT_PORT.postgresql));
  const [database, setDatabase] = useState('');
  const [user, setUser] = useState('');
  const [password, setPassword] = useState('');

  const sqlPort = parsePort(port, SQL_DEFAULT_PORT[databaseType]);
  const duplicateName = catalogs.some((catalog) => catalog.name === name.trim());
  const canSubmit =
    name.trim().length > 0 &&
    !duplicateName &&
    warehouse.trim().length > 0 &&
    (type !== 'rest' || uri.trim().length > 0) &&
    (type !== 'sql' ||
      (host.trim().length > 0 &&
        database.trim().length > 0 &&
        user.trim().length > 0 &&
        sqlPort !== undefined));

  function changeDatabaseType(next: SqlNetworkDatabaseType) {
    const previousDefault = String(SQL_DEFAULT_PORT[databaseType]);
    setDatabaseType(next);
    if (port.trim() === '' || port.trim() === previousDefault) {
      setPort(String(SQL_DEFAULT_PORT[next]));
    }
  }

  function reset() {
    setName('');
    setWarehouse('');
    setError(null);
    setErrorCode(null);
    setConnectStatus(null);
    setRegion('');
    setEndpoint('');
    setAccessKey('');
    setSecretKey('');
    setGlueId('');
    setUri('');
    setToken('');
    setCredential('');
    setOauth2Uri('');
    setRestAuthType('');
    setScope('');
    setSigningName('');
    setSigningRegion('');
    setSigningV4(true);
    setNoIdentifierFields(false);
    setDatabaseType('postgresql');
    setHost('');
    setPort(String(SQL_DEFAULT_PORT.postgresql));
    setDatabase('');
    setUser('');
    setPassword('');
  }

  function cancelConnection() {
    connectAbortRef.current?.abort('cancelled');
    setConnectStatus(null);
  }

  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      window.setTimeout(() => closeButtonRef.current?.focus(), 0);
      return;
    }

    reset();
    previousFocusRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !connectStatus) onClose();
    }

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [connectStatus, onClose, open]);

  useEffect(() => {
    return () => {
      connectAbortRef.current?.abort();
      if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    };
  }, []);

  function trapFocus(event: React.KeyboardEvent<HTMLElement>) {
    if (event.key !== 'Tab') return;
    const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable || focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function s3Fields() {
    return {
      region: omitEmpty(region),
      endpoint: omitEmpty(endpoint),
      access_key: omitEmpty(accessKey),
      secret_key: omitEmpty(secretKey),
    };
  }

  function buildBody(): CatalogCreateRequest {
    const base = {
      lakehouse: 'iceberg' as const,
      name: name.trim(),
      warehouse: warehouse.trim(),
      ...s3Fields(),
    };
    if (type === 'glue') {
      return {
        ...base,
        catalog_type: 'glue',
        glue_catalog_id: omitEmpty(glueId),
      };
    }
    if (type === 'rest') {
      return {
        ...base,
        catalog_type: 'rest',
        rest_catalog_url: uri.trim(),
        token: omitEmpty(token),
        credential: omitEmpty(credential),
        oauth2_uri: omitEmpty(oauth2Uri),
        rest_auth_type: omitEmpty(restAuthType),
        scope: omitEmpty(scope),
        rest_signing_name: omitEmpty(signingName),
        rest_signing_region: omitEmpty(signingRegion),
        rest_signing_v_4: signingV4,
        no_identifier_fields: noIdentifierFields,
      };
    }
    return {
      ...base,
      catalog_type: 'sql',
      database_type: databaseType,
      host: host.trim(),
      port: sqlPort,
      username: user.trim(),
      password,
      database: database.trim(),
    };
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (connectStatus) return;
    if (!canSubmit) {
      const message = duplicateName
        ? 'Choose a unique catalog name.'
        : 'Complete the required fields and correct any invalid values.';
      setError(message);
      event.currentTarget.querySelector<HTMLElement>(':invalid')?.focus();
      return;
    }
    const catalogName = name.trim();
    const controller = new AbortController();
    connectAbortRef.current = controller;
    setConnectStatus('connecting');
    setError(null);
    setErrorCode(null);
    // TODO(backend): the server-side catalog test also needs an enforced timeout.
    timeoutRef.current = window.setTimeout(
      () => controller.abort('timeout'),
      CONNECTION_TIMEOUT_MS,
    );
    try {
      await addCatalog(buildBody(), controller.signal);
      reset();
      onClose();
      notify({ tone: 'success', message: `Connected ${catalogName}.` });
    } catch (err) {
      if (controller.signal.reason === 'cancelled') return;
      const timedOut = controller.signal.reason === 'timeout';
      if (timedOut) {
        const latest = await refreshCatalogs();
        if (latest?.some((catalog) => catalog.name === catalogName)) {
          reset();
          onClose();
          notify({ tone: 'success', message: `Connected ${catalogName}.` });
          return;
        }
      }
      const presentation = err instanceof ApiError ? presentError(err.body?.code) : presentError();
      const message = timedOut
        ? 'The connection attempt took longer than 30 seconds. The catalog may still be created; refresh before retrying the same name.'
        : err instanceof ApiError
          ? err.message
          : 'Failed to connect to the catalog.';
      setError(message);
      setErrorCode(err instanceof ApiError ? err.body?.code ?? null : null);
      setConnectStatus('error');
      if (!timedOut && !(err instanceof ApiError)) {
        setError(`${presentation.title}. ${presentation.hint}`);
      }
    } finally {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      connectAbortRef.current = null;
    }
  }

  const busy = connectStatus !== null;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => {
              if (!busy) onClose();
            }}
            className="fixed inset-0 z-overlay bg-ink/10"
          />

          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label="Add catalog"
            ref={panelRef}
            onKeyDown={trapFocus}
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed right-0 top-0 z-panel flex h-full w-full flex-col border-l border-line bg-panel shadow-pop sm:w-[460px]"
          >
            <div className="flex h-header shrink-0 items-center border-b border-line px-5">
              <h2 className="text-[13px] font-medium text-ink">Add catalog</h2>
              <IconButton
                onClick={onClose}
                disabled={busy}
                ref={closeButtonRef}
                label="Close"
                className="ml-auto h-6 w-6 border-0"
              >
                <XIcon className="h-4 w-4" strokeWidth={2} />
              </IconButton>
            </div>

            <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
              <div className="lg-scroll flex-1 space-y-6 overflow-y-auto px-5 py-5">
                <section>
                  <h3 className="mb-2 text-2xs font-medium uppercase tracking-wider text-ink-faint">
                    Catalog type
                  </h3>
                  <div className="grid grid-cols-3 gap-2">
                    {typeOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setType(option.value)}
                        aria-pressed={type === option.value}
                        className={`rounded-lg border px-2.5 py-2 text-left transition-colors duration-150 ${
                          type === option.value
                            ? 'border-accent bg-accent-soft'
                            : 'border-line hover:border-line-strong hover:bg-line-soft/60'
                        }`}
                      >
                        <div className="font-mono text-[12px] font-medium text-ink">{option.title}</div>
                        <div className="mt-0.5 text-[11px] leading-tight text-ink-muted">
                          {option.description}
                        </div>
                      </button>
                    ))}
                  </div>
                </section>

                <section className="space-y-3">
                  <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                    Identity
                  </h3>
                  <Field
                    label="Catalog name"
                    value={name}
                    onChange={setName}
                    placeholder="production"
                    mono
                    required
                    hint={duplicateName ? 'A catalog with this name already exists.' : undefined}
                  />
                  <Field
                    label="Warehouse location"
                    value={warehouse}
                    onChange={setWarehouse}
                    placeholder="s3://bucket/warehouse"
                    mono
                    required
                  />
                </section>

                <section className="space-y-3">
                  <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                    Object storage
                  </h3>
                  <Field
                    label="Region"
                    value={region}
                    onChange={setRegion}
                    placeholder="us-east-1"
                    mono
                  />
                  <Field
                    label="S3 endpoint"
                    value={endpoint}
                    onChange={setEndpoint}
                    placeholder="https://s3.amazonaws.com"
                    mono
                  />
                  <Field
                    label="Access key ID"
                    value={accessKey}
                    onChange={setAccessKey}
                    placeholder="AKIA…"
                    mono
                    hint="Leave blank to use the default AWS credential chain."
                  />
                  <Field
                    label="Secret access key"
                    value={secretKey}
                    onChange={setSecretKey}
                    placeholder="••••••••••••••••"
                    secret
                  />
                </section>

                {type === 'glue' && (
                  <section className="space-y-3">
                    <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                      Glue
                    </h3>
                    <Field
                      label="Glue catalog ID"
                      value={glueId}
                      onChange={setGlueId}
                      placeholder="123456789012"
                      mono
                    />
                  </section>
                )}

                {type === 'rest' && (
                  <section className="space-y-3">
                    <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                      REST catalog
                    </h3>
                    <Field
                      label="Catalog URI"
                      value={uri}
                      onChange={setUri}
                      placeholder="https://catalog.internal/api"
                      mono
                      required
                    />
                    <Field
                      label="Auth type"
                      value={restAuthType}
                      onChange={setRestAuthType}
                      placeholder="oauth2"
                      mono
                    />
                    <Field
                      label="Bearer token"
                      value={token}
                      onChange={setToken}
                      placeholder="optional"
                      secret
                    />
                    <Field
                      label="Credential"
                      value={credential}
                      onChange={setCredential}
                      placeholder="client:secret"
                      secret
                    />
                    <Field
                      label="OAuth2 server URI"
                      value={oauth2Uri}
                      onChange={setOauth2Uri}
                      placeholder="https://auth.internal/oauth2/token"
                      mono
                    />
                    <Field
                      label="OAuth2 scope"
                      value={scope}
                      onChange={setScope}
                      placeholder="catalog"
                      mono
                    />
                    <Field
                      label="SigV4 signing name"
                      value={signingName}
                      onChange={setSigningName}
                      placeholder="execute-api"
                      mono
                    />
                    <Field
                      label="SigV4 signing region"
                      value={signingRegion}
                      onChange={setSigningRegion}
                      placeholder="us-east-1"
                      mono
                    />
                    <Checkbox
                      label="Sign REST requests with AWS SigV4"
                      checked={signingV4}
                      onChange={setSigningV4}
                    />
                    <Checkbox
                      label="Omit identifier fields in REST requests"
                      checked={noIdentifierFields}
                      onChange={setNoIdentifierFields}
                    />
                  </section>
                )}

                {type === 'sql' && (
                  <section className="space-y-3">
                    <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                      SQL backend
                    </h3>
                    <Select
                      label="Database type"
                      value={databaseType}
                      onChange={(value) => changeDatabaseType(value as SqlNetworkDatabaseType)}
                      options={[
                        { value: 'postgresql', label: 'PostgreSQL' },
                        { value: 'mysql', label: 'MySQL' },
                      ]}
                    />
                    <div className="grid grid-cols-[1fr_96px] gap-3">
                      <Field
                        label="Host"
                        value={host}
                        onChange={setHost}
                        placeholder="db.internal"
                        mono
                        required
                      />
                      <Field
                        label="Port"
                        value={port}
                        onChange={setPort}
                        placeholder={String(SQL_DEFAULT_PORT[databaseType])}
                        mono
                        hint={sqlPort === undefined ? 'Port must be 1–65535.' : undefined}
                      />
                    </div>
                    <Field
                      label="Database"
                      value={database}
                      onChange={setDatabase}
                      placeholder="iceberg_catalog"
                      mono
                      required
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <Field
                        label="Username"
                        value={user}
                        onChange={setUser}
                        placeholder="lakegen"
                        mono
                        required
                      />
                      <Field
                        label="Password"
                        value={password}
                        onChange={setPassword}
                        placeholder="••••••••"
                        secret
                      />
                    </div>
                  </section>
                )}

                {error && !connectStatus && <p className="text-[13px] text-err">{error}</p>}
              </div>

              <div className="flex shrink-0 items-center gap-2 border-t border-line px-5 py-3">
                <Button variant="ghost" onClick={onClose} disabled={busy}>
                  Cancel
                </Button>
                <span className="ml-auto" />
                <Button type="submit" variant="primary" disabled={busy}>
                  Connect
                </Button>
              </div>
            </form>
          </motion.aside>

          <ConnectStatusDialog
            status={connectStatus}
            catalogName={name.trim()}
            message={error}
            errorCode={errorCode}
            onCancel={cancelConnection}
            onBack={() => setConnectStatus(null)}
            onClose={onClose}
          />
        </>
      )}
    </AnimatePresence>
  );
}
