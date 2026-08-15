import React, { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { XIcon } from 'lucide-react';
import type { CatalogCreateRequest, CatalogType } from '../../api/types';
import { ApiError } from '../../api/client';
import { useLakeGen } from '../../state/LakeGenContext';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { Select } from '../ui/Select';

const typeOptions: { value: CatalogType; title: string; description: string }[] = [
  { value: 'glue', title: 'Glue', description: 'AWS Glue Data Catalog' },
  { value: 'rest', title: 'REST', description: 'Iceberg REST catalog' },
  { value: 'sql', title: 'SQL', description: 'JDBC-backed catalog' },
];

interface AddCatalogPanelProps {
  open: boolean;
  onClose: () => void;
}

function omitEmpty(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function AddCatalogPanel({ open, onClose }: AddCatalogPanelProps) {
  const { addCatalog } = useLakeGen();
  const [type, setType] = useState<CatalogType>('glue');
  const [name, setName] = useState('');
  const [warehouse, setWarehouse] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [glueId, setGlueId] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');

  const [uri, setUri] = useState('');
  const [token, setToken] = useState('');
  const [credential, setCredential] = useState('');

  const [host, setHost] = useState('');
  const [port, setPort] = useState('');
  const [database, setDatabase] = useState('');
  const [user, setUser] = useState('');
  const [password, setPassword] = useState('');

  const canSubmit =
    name.trim().length > 0 &&
    warehouse.trim().length > 0 &&
    (type !== 'rest' || uri.trim().length > 0) &&
    (type !== 'sql' ||
      (host.trim().length > 0 && database.trim().length > 0 && user.trim().length > 0));

  function reset() {
    setName('');
    setWarehouse('');
    setError(null);
    setGlueId('');
    setAccessKey('');
    setSecretKey('');
    setUri('');
    setToken('');
    setCredential('');
    setHost('');
    setDatabase('');
    setUser('');
    setPassword('');
  }

  function buildBody(): CatalogCreateRequest {
    const base = {
      lakehouse: 'iceberg' as const,
      name: name.trim(),
      warehouse: warehouse.trim(),
    };
    if (type === 'glue') {
      return {
        ...base,
        catalog_type: 'glue',
        glue_catalog_id: omitEmpty(glueId),
        region: omitEmpty(region),
        access_key: omitEmpty(accessKey),
        secret_key: omitEmpty(secretKey),
      };
    }
    if (type === 'rest') {
      return {
        ...base,
        catalog_type: 'rest',
        rest_catalog_url: uri.trim(),
        token: omitEmpty(token),
        credential: omitEmpty(credential),
      };
    }
    return {
      ...base,
      catalog_type: 'sql',
      database_type: 'postgresql',
      host: host.trim(),
      port: Number(port) || 3306,
      username: user.trim(),
      password,
      database: database.trim(),
    };
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await addCatalog(buildBody());
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to add catalog');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-30 bg-ink/10"
          />

          <motion.aside
            role="dialog"
            aria-label="Add catalog"
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed right-0 top-0 z-40 flex h-full w-[460px] flex-col border-l border-line bg-panel shadow-pop"
          >
            <div className="flex h-[52px] shrink-0 items-center border-b border-line px-5">
              <h2 className="text-[13px] font-medium text-ink">Add catalog</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="ml-auto flex h-6 w-6 items-center justify-center rounded text-ink-faint transition-colors hover:bg-line-soft hover:text-ink"
              >
                <XIcon className="h-4 w-4" strokeWidth={2} />
              </button>
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
                  <Field label="Catalog name" value={name} onChange={setName} placeholder="production" mono />
                  <Field
                    label="Warehouse location"
                    value={warehouse}
                    onChange={setWarehouse}
                    placeholder="s3://bucket/warehouse"
                    mono
                  />
                </section>

                {type === 'glue' && (
                  <section className="space-y-3">
                    <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                      Glue &amp; S3
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      <Field
                        label="Glue catalog ID"
                        value={glueId}
                        onChange={setGlueId}
                        placeholder="123456789012"
                        mono
                      />
                      <Select
                        label="Region"
                        value={region}
                        onChange={setRegion}
                        options={[
                          { value: 'us-east-1', label: 'us-east-1' },
                          { value: 'us-west-2', label: 'us-west-2' },
                          { value: 'eu-west-1', label: 'eu-west-1' },
                          { value: 'ap-south-1', label: 'ap-south-1' },
                        ]}
                      />
                    </div>
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
                )}

                {type === 'rest' && (
                  <section className="space-y-3">
                    <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                      REST endpoint
                    </h3>
                    <Field
                      label="Catalog URI"
                      value={uri}
                      onChange={setUri}
                      placeholder="https://catalog.internal/api"
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
                      placeholder="optional client:secret"
                      secret
                    />
                  </section>
                )}

                {type === 'sql' && (
                  <section className="space-y-3">
                    <h3 className="text-2xs font-medium uppercase tracking-wider text-ink-faint">
                      SQL backend
                    </h3>
                    <div className="grid grid-cols-[1fr_96px] gap-3">
                      <Field label="Host" value={host} onChange={setHost} placeholder="db.internal" mono />
                      <Field label="Port" value={port} onChange={setPort} mono />
                    </div>
                    <Field
                      label="Database"
                      value={database}
                      onChange={setDatabase}
                      placeholder="iceberg_catalog"
                      mono
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Username" value={user} onChange={setUser} placeholder="lakegen" mono />
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

                {error && <p className="text-[13px] text-err">{error}</p>}
              </div>

              <div className="flex shrink-0 items-center gap-2 border-t border-line px-5 py-3">
                <Button variant="ghost" onClick={onClose}>
                  Cancel
                </Button>
                <span className="ml-auto" />
                <Button type="submit" variant="primary" disabled={!canSubmit || submitting}>
                  {submitting ? 'Adding…' : 'Add catalog'}
                </Button>
              </div>
            </form>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
