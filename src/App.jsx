import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Code2,
  Copy,
  Download,
  ExternalLink,
  Eye,
  FileText,
  History as HistoryIcon,
  Image as ImageIcon,
  KeyRound,
  Loader2,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  WandSparkles,
  X,
} from 'lucide-react';

const API_BASE = '/api';

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error('The local app service is not responding. Close and reopen the app, then try again.');
  }
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) {
    throw new Error(data?.detail || 'That action could not be completed. Please try again.');
  }
  return data;
}

const initialSettings = { api_key_configured: false, model: 'gpt-4o-mini' };
const statusLabels = {
  opening: 'Opening product page',
  waiting: 'Waiting for product page',
  verification_required: 'Human verification needed',
  extracting: 'Extracting product information',
  completed: 'Product details ready',
  failed: 'Could not extract product',
  cancelled: 'Extraction stopped',
};

function BrandMark() {
  return (
    <div className="brand-lockup">
      <div className="brand-mark"><span>PP</span><i /></div>
      <div className="brand-copy">
        <strong>PRIMEPICK</strong>
        <span>GOODS · LISTING STUDIO</span>
      </div>
    </div>
  );
}

function FieldArray({ title, items, onChange, placeholder, emptyLabel, helpText, maxLength = 1_000 }) {
  const safeItems = Array.isArray(items) ? items : [];
  const updateItem = (index, value) => onChange(safeItems.map((item, itemIndex) => itemIndex === index ? value : item));
  const removeItem = (index) => onChange(safeItems.filter((_, itemIndex) => itemIndex !== index));
  return (
    <section className="editor-section">
      <div className="editor-section-heading">
        <div>
          <h3>{title}</h3>
          {helpText && <p>{helpText}</p>}
        </div>
        <button className="button button-quiet button-small" onClick={() => onChange([...safeItems, ''])} type="button">
          <Plus size={15} /> Add
        </button>
      </div>
      {safeItems.length === 0 ? (
        <div className="empty-inline">{emptyLabel || 'No items added.'}</div>
      ) : (
        <div className="array-editor">
          {safeItems.map((item, index) => (
            <div className="array-row" key={`${title}-${index}`}>
              <span className="array-number">{String(index + 1).padStart(2, '0')}</span>
              <textarea
                rows={1}
                maxLength={maxLength}
                value={item}
                onChange={(event) => updateItem(index, event.target.value)}
                placeholder={placeholder}
              />
              <button className="icon-button muted-icon" onClick={() => removeItem(index)} type="button" aria-label={`Remove ${title} item`}>
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SpecificationEditor({ items, onChange }) {
  const rows = Array.isArray(items) ? items : [];
  const update = (index, key, value) => onChange(rows.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item));
  return (
    <section className="editor-section">
      <div className="editor-section-heading">
        <div>
          <h3>Product specifications</h3>
          <p>Keep only details confirmed on the source product page.</p>
        </div>
        <button className="button button-quiet button-small" onClick={() => onChange([...rows, { name: '', value: '' }])} type="button">
          <Plus size={15} /> Add
        </button>
      </div>
      {rows.length === 0 ? <div className="empty-inline">No specifications added yet.</div> : (
        <div className="spec-editor">
          {rows.map((row, index) => (
            <div className="spec-edit-row" key={`spec-${index}`}>
              <input aria-label="Specification name" maxLength={500} value={row.name} onChange={(event) => update(index, 'name', event.target.value)} placeholder="Name" />
              <input aria-label="Specification value" maxLength={2000} value={row.value} onChange={(event) => update(index, 'value', event.target.value)} placeholder="Value" />
              <button className="icon-button muted-icon" onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))} type="button" aria-label="Remove specification"><Trash2 size={15} /></button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function App() {
  const [page, setPage] = useState('workspace');
  const [tab, setTab] = useState('product');
  const [url, setUrl] = useState('');
  const [job, setJob] = useState(null);
  const [product, setProduct] = useState(null);
  const [content, setContent] = useState(null);
  const [html, setHtml] = useState('');
  const [previewMode, setPreviewMode] = useState('preview');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [settings, setSettings] = useState(initialSettings);
  const [apiKey, setApiKey] = useState('');
  const [settingsModel, setSettingsModel] = useState(initialSettings.model);
  const [clearSavedKey, setClearSavedKey] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const [savedListingId, setSavedListingId] = useState(null);
  const toastTimer = useRef(null);
  const inputRef = useRef(null);

  const notify = useCallback((message, tone = 'success') => {
    setToast({ message, tone });
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3500);
  }, []);

  const refreshSettings = useCallback(async () => {
    try {
      const result = await api('/settings');
      setSettings(result);
      setSettingsModel(result.model || 'gpt-4o-mini');
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const items = await api('/listings');
      setHistory(items || []);
    } catch {
      // The workspace can still be used if history is temporarily unavailable.
    }
  }, []);

  useEffect(() => {
    refreshSettings();
    refreshHistory();
    const heartbeat = window.setInterval(() => {
      api('/health').then(() => setBackendOnline(true)).catch(() => setBackendOnline(false));
    }, 12_000);
    return () => {
      window.clearInterval(heartbeat);
      window.clearTimeout(toastTimer.current);
    };
  }, [refreshSettings, refreshHistory]);

  useEffect(() => {
    if (!job?.id || ['completed', 'failed', 'cancelled'].includes(job.status)) return undefined;
    let stopped = false;
    const poll = async () => {
      try {
        const result = await api(`/extractions/${job.id}`);
        if (stopped) return;
        setJob(result);
        if (result.status === 'completed') {
          setProduct(result.product);
          setContent(null);
          setHtml('');
          setSavedListingId(null);
          setBusy('');
          notify('Product details are ready to review.');
        } else if (result.status === 'failed' || result.status === 'cancelled') {
          setBusy('');
          if (result.status === 'failed') setError(result.message);
        }
      } catch (requestError) {
        if (!stopped) {
          setError(requestError.message);
          setBusy('');
        }
      }
    };
    poll();
    const timer = window.setInterval(poll, 1600);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status, notify]);

  const startExtraction = async (event) => {
    event?.preventDefault();
    setError('');
    if (!url.trim()) {
      setError('Paste an AliExpress product link to get started.');
      inputRef.current?.focus();
      return;
    }
    setBusy('extracting');
    setProduct(null);
    setContent(null);
    setHtml('');
    setSavedListingId(null);
    setJob(null);
    setPage('workspace');
    setTab('product');
    try {
      const result = await api('/extractions', { method: 'POST', body: JSON.stringify({ url: url.trim() }) });
      setJob(result);
    } catch (requestError) {
      setBusy('');
      setError(requestError.message);
    }
  };

  const continueAfterVerification = async () => {
    if (!job?.id) return;
    try {
      await api(`/extractions/${job.id}/continue`, { method: 'POST' });
      setJob((current) => current ? { ...current, status: 'waiting', message: 'Checking the product page after verification...' } : current);
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const cancelExtraction = async () => {
    if (!job?.id) return;
    try {
      await api(`/extractions/${job.id}/cancel`, { method: 'POST' });
    } catch {
      // Update the local workspace even if the backend is already closing the browser.
    }
    setJob((current) => current ? { ...current, status: 'cancelled', message: 'Extraction stopped.' } : current);
    setBusy('');
  };

  const updateProduct = (key, value) => {
    setProduct((current) => current ? { ...current, [key]: value } : current);
    setHtml('');
    setSavedListingId(null);
  };

  const toggleImage = (index) => {
    const selectedCount = product.images.filter((image) => image.selected).length;
    const selected = product.images[index]?.selected;
    if (selected && selectedCount <= 1) {
      notify('Keep at least one image selected for the listing.', 'warning');
      return;
    }
    updateProduct('images', product.images.map((image, imageIndex) => imageIndex === index ? { ...image, selected: !image.selected } : image));
  };

  const generateCopy = async () => {
    if (!product) return;
    setError('');
    setBusy('generating');
    try {
      const result = await api('/generate', { method: 'POST', body: JSON.stringify({ product }) });
      setContent(result.content);
      setHtml('');
      setSavedListingId(null);
      setTab('copy');
      notify('Your eBay listing draft is ready to edit.');
    } catch (requestError) {
      setError(requestError.message);
      if (requestError.message.toLowerCase().includes('api key')) {
        notify('Add your OpenAI API key in Settings to generate listing copy.', 'warning');
      }
    } finally {
      setBusy('');
    }
  };

  const renderHtml = async (switchToPreview = true) => {
    if (!product || !content) return '';
    setError('');
    setBusy('rendering');
    try {
      const result = await api('/render', { method: 'POST', body: JSON.stringify({ product, content }) });
      setHtml(result.html);
      if (switchToPreview) {
        setTab('preview');
        setPreviewMode('preview');
      }
      return result.html;
    } catch (requestError) {
      setError(requestError.message);
      return '';
    } finally {
      setBusy('');
    }
  };

  const copyHtml = async () => {
    const source = html || await renderHtml(false);
    if (!source) return false;
    try {
      await navigator.clipboard.writeText(source);
      notify('Complete HTML copied to your clipboard.');
      return true;
    } catch {
      notify('Clipboard access was blocked. Use the HTML source view to select and copy.', 'warning');
      setPreviewMode('source');
      return false;
    }
  };

  const downloadHtml = async () => {
    const source = html || await renderHtml(false);
    if (!source) return;
    const blob = new Blob([source], { type: 'text/html;charset=utf-8' });
    const link = document.createElement('a');
    const downloadUrl = URL.createObjectURL(blob);
    link.href = downloadUrl;
    link.download = `${(content?.title || 'primepick-listing').replace(/[^a-z0-9-_ ]/gi, '').trim().replace(/\s+/g, '-').slice(0, 70) || 'primepick-listing'}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
    notify('HTML listing downloaded.');
  };

  const saveListing = async () => {
    if (!product || !content) return;
    setBusy('saving');
    setError('');
    try {
      const result = await api('/listings', { method: 'POST', body: JSON.stringify({ product, content }) });
      setSavedListingId(result.id);
      await refreshHistory();
      notify('Listing saved to local history.');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy('');
    }
  };

  const loadHistoryItem = async (id) => {
    setHistoryLoading(true);
    setError('');
    try {
      const result = await api(`/listings/${id}`);
      setProduct(result.product);
      setContent(result.content);
      setHtml(result.html);
      setUrl(result.source_url);
      setSavedListingId(result.id);
      setPage('workspace');
      setTab('preview');
      setPreviewMode('preview');
      setJob(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setHistoryLoading(false);
    }
  };

  const saveSettings = async (event) => {
    event.preventDefault();
    setBusy('settings');
    setError('');
    const body = { model: settingsModel, clear_api_key: clearSavedKey };
    if (apiKey.trim()) body.api_key = apiKey.trim();
    try {
      const result = await api('/settings', { method: 'PUT', body: JSON.stringify(body) });
      setSettings(result);
      setSettingsModel(result.model || 'gpt-4o-mini');
      setApiKey('');
      setClearSavedKey(false);
      notify('Settings saved on this computer.');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy('');
    }
  };

  const selectedImageCount = useMemo(() => product?.images?.filter((image) => image.selected).length || 0, [product]);
  const productStepDone = Boolean(product);
  const copyStepDone = Boolean(content);
  const previewStepDone = Boolean(html);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <BrandMark />
        <div className="sidebar-workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={`nav-item ${page === 'workspace' ? 'active' : ''}`} onClick={() => setPage('workspace')} type="button">
            <Sparkles size={18} strokeWidth={1.8} /><span>New listing</span><ChevronRight className="nav-chevron" size={15} />
          </button>
          <button className={`nav-item ${page === 'history' ? 'active' : ''}`} onClick={() => { setPage('history'); refreshHistory(); }} type="button">
            <HistoryIcon size={18} strokeWidth={1.8} /><span>Listing history</span><span className="nav-count">{history.length}</span>
          </button>
        </nav>
        <div className="sidebar-divider" />
        <button className={`nav-item ${page === 'settings' ? 'active' : ''}`} onClick={() => { setPage('settings'); setError(''); refreshSettings(); }} type="button">
          <KeyRound size={18} strokeWidth={1.8} /><span>Settings</span><ChevronRight className="nav-chevron" size={15} />
        </button>
        <div className="sidebar-bottom">
          <div className="local-badge"><span className={backendOnline ? 'online-dot' : 'offline-dot'} />{backendOnline ? 'Local workspace' : 'Service disconnected'}</div>
          <p>Your listings and settings stay on this computer.</p>
          <div className="sidebar-version">PRIMEPICK GOODS <span>·</span> 0.1.0</div>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div className="breadcrumb"><span>PrimePick Goods</span><ChevronRight size={14} /><strong>{page === 'workspace' ? 'Listing studio' : page === 'history' ? 'Listing history' : 'Settings'}</strong></div>
          <div className="topbar-right">
            <span className="market-pill"><span className="market-dot" /> EBAY US</span>
            <span className="local-pill"><LockKeyhole size={13} /> LOCAL APP</span>
          </div>
        </header>

        {error && (
          <div className="global-alert" role="alert">
            <CircleAlert size={17} /><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error" type="button"><X size={16} /></button>
          </div>
        )}

        {page === 'workspace' && (
          <div className="page-content workspace-page">
            <div className="page-heading-row">
              <div>
                <div className="eyebrow"><span className="eyebrow-line" /> EBAY LISTING WORKSPACE</div>
                <h1>{product ? 'Your listing workspace' : 'Turn a product link into a polished listing.'}</h1>
                <p className="page-subtitle">{product ? 'Review the extracted details, refine the copy, then preview your branded listing.' : 'Start with an AliExpress product URL. We’ll help you build a ready-to-use eBay description.'}</p>
              </div>
              {product && <button className="button button-secondary new-listing-button" onClick={() => { setProduct(null); setContent(null); setHtml(''); setJob(null); setUrl(''); setError(''); setTab('product'); setSavedListingId(null); inputRef.current?.focus(); }} type="button"><Plus size={16} /> New listing</button>}
            </div>

            <section className="url-card">
              <div className="url-card-icon"><LinkIcon /></div>
              <div className="url-card-copy">
                <label htmlFor="product-url">AliExpress product URL</label>
                <p>Paste a public product link. Chromium will open so you can complete any verification yourself.</p>
              </div>
              <form className="url-form" onSubmit={startExtraction}>
                <div className="url-input-wrap">
                  <ExternalLink size={17} />
                  <input ref={inputRef} id="product-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.aliexpress.com/item/..." disabled={busy === 'extracting'} />
                  {url && <button className="clear-url" type="button" aria-label="Clear URL" onClick={() => setUrl('')}><X size={15} /></button>}
                </div>
                <button className="button button-primary extract-button" disabled={busy === 'extracting'} type="submit">
                  {busy === 'extracting' ? <Loader2 className="spin" size={17} /> : <WandSparkles size={17} />}
                  {busy === 'extracting' ? 'Working…' : 'Extract product'}
                </button>
              </form>
              <div className="url-card-footer"><ShieldCheck size={15} /><span>No CAPTCHA bypass. Verification is completed manually in the visible browser.</span><span className="footer-separator">·</span><span>Product facts are checked before publishing.</span></div>
            </section>

            {job && ['opening', 'waiting', 'verification_required', 'extracting'].includes(job.status) && (
              <section className={`progress-card ${job.status === 'verification_required' ? 'verification-card' : ''}`} aria-live="polite">
                <div className={`progress-icon ${job.status === 'verification_required' ? 'verification-icon' : ''}`}>
                  {job.status === 'verification_required' ? <ShieldCheck size={19} /> : <Loader2 className="spin" size={19} />}
                </div>
                <div className="progress-copy">
                  <strong>{statusLabels[job.status] || 'Working on your product'}</strong>
                  <p>{job.message}</p>
                  {job.status === 'verification_required' && <span className="verification-hint">Switch to the Chromium window, complete the challenge there, then continue below.</span>}
                </div>
                <div className="progress-actions">
                  {job.status === 'verification_required' && <button className="button button-primary button-small" onClick={continueAfterVerification} type="button"><Check size={15} /> Continue</button>}
                  <button className="button button-quiet button-small" onClick={cancelExtraction} type="button">Cancel</button>
                </div>
              </section>
            )}

            {product && (
              <>
                <div className="workflow-bar">
                  <div className="workflow-steps">
                    <button className={`workflow-step ${tab === 'product' ? 'selected' : ''} ${productStepDone ? 'done' : ''}`} onClick={() => setTab('product')} type="button">
                      <span className="step-number">{productStepDone ? <Check size={13} /> : '1'}</span><span>Product details</span>
                    </button>
                    <span className="step-connector" />
                    <button className={`workflow-step ${tab === 'copy' ? 'selected' : ''} ${copyStepDone ? 'done' : ''}`} onClick={() => content && setTab('copy')} disabled={!content} type="button">
                      <span className="step-number">{copyStepDone ? <Check size={13} /> : '2'}</span><span>Listing copy</span>
                    </button>
                    <span className="step-connector" />
                    <button className={`workflow-step ${tab === 'preview' ? 'selected' : ''} ${previewStepDone ? 'done' : ''}`} onClick={() => content && setTab('preview')} disabled={!content} type="button">
                      <span className="step-number">{previewStepDone ? <Check size={13} /> : '3'}</span><span>HTML preview</span>
                    </button>
                  </div>
                  {content && <div className="workflow-status"><BadgeCheck size={15} /> Draft ready</div>}
                </div>

                {tab === 'product' && <ProductReview product={product} selectedImageCount={selectedImageCount} toggleImage={toggleImage} updateProduct={updateProduct} onGenerate={generateCopy} busy={busy} apiKeyConfigured={settings.api_key_configured} onSettings={() => setPage('settings')} />}
                {tab === 'copy' && content && <ContentEditor content={content} setContent={(next) => { setContent(next); setHtml(''); setSavedListingId(null); }} busy={busy} onPreview={() => renderHtml(true)} onBack={() => setTab('product')} />}
                {tab === 'preview' && content && <PreviewPanel html={html} mode={previewMode} setMode={setPreviewMode} busy={busy} onRefresh={() => renderHtml(false)} onCopy={copyHtml} onDownload={downloadHtml} onSave={saveListing} savedListingId={savedListingId} onEdit={() => setTab('copy')} />}
              </>
            )}

            {!product && !job && (
              <div className="getting-started-row">
                <div className="start-note"><div className="start-note-icon"><Sparkles size={17} /></div><div><strong>Built for accurate listings</strong><span>Product facts are carried forward without inventing specs or claims.</span></div></div>
                <div className="start-note"><div className="start-note-icon gold"><ImageIcon size={17} /></div><div><strong>You stay in control</strong><span>Review images, edit every field, and approve the final HTML.</span></div></div>
                <div className="start-note"><div className="start-note-icon green"><LockKeyhole size={16} /></div><div><strong>Local by design</strong><span>History and settings are saved on this computer.</span></div></div>
              </div>
            )}
          </div>
        )}

        {page === 'history' && (
          <HistoryPage items={history} loading={historyLoading} reload={refreshHistory} onOpen={loadHistoryItem} />
        )}

        {page === 'settings' && (
          <SettingsPage
            settings={settings}
            apiKey={apiKey}
            setApiKey={setApiKey}
            model={settingsModel}
            setModel={setSettingsModel}
            clearSavedKey={clearSavedKey}
            setClearSavedKey={setClearSavedKey}
            busy={busy}
            onSave={saveSettings}
          />
        )}
      </main>

      {toast && <div className={`toast toast-${toast.tone}`} role="status"><span className="toast-check">{toast.tone === 'warning' ? <CircleAlert size={16} /> : <CheckCircle2 size={16} />}</span>{toast.message}<button onClick={() => setToast(null)} type="button" aria-label="Dismiss notification"><X size={15} /></button></div>}
    </div>
  );
}

function LinkIcon() {
  return <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M10 13.8a4.6 4.6 0 0 0 6.5 0l3.1-3.1a4.6 4.6 0 0 0-6.5-6.5l-1.8 1.8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/><path d="M14 10.2a4.6 4.6 0 0 0-6.5 0l-3.1 3.1a4.6 4.6 0 0 0 6.5 6.5l1.8-1.8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>;
}

function ProductReview({ product, selectedImageCount, toggleImage, updateProduct, onGenerate, busy, apiKeyConfigured, onSettings }) {
  return (
    <div className="review-layout">
      <div className="review-main-column">
        {product.missing_info?.length > 0 && (
          <div className="review-alert"><div className="review-alert-icon"><CircleAlert size={17} /></div><div><strong>Review before generating</strong><p>Some product details weren’t detected. Add what you can confirm, or keep the notes for later.</p><ul>{product.missing_info.map((note, index) => <li key={`missing-${index}`}>{note}</li>)}</ul></div></div>
        )}
        <section className="panel product-details-panel">
          <div className="panel-heading">
            <div className="panel-heading-icon navy"><FileText size={18} /></div>
            <div><h2>Product information</h2><p>Check the source details and add anything the page didn’t show.</p></div>
            <span className="extracted-tag"><CheckCircle2 size={13} /> EXTRACTED</span>
          </div>
          <div className="product-fields">
            <label className="field-label" htmlFor="source-title">Product title <span>from source</span></label>
            <input id="source-title" className="text-input" maxLength={1500} value={product.title || ''} onChange={(event) => updateProduct('title', event.target.value)} placeholder="Add the product title" />
            <div className="field-label-row"><label className="field-label" htmlFor="source-description">Product description</label><span className="character-count">{(product.description || '').length.toLocaleString()} / 30,000</span></div>
            <textarea id="source-description" className="text-area source-description" maxLength={30000} value={product.description || ''} onChange={(event) => updateProduct('description', event.target.value)} placeholder="Add the product details you can confirm from the source page." rows={6} />
          </div>

          <div className="detail-grid">
            <div className="detail-block">
              <div className="detail-block-title"><span>Specifications</span><span className="detail-count">{product.specifications?.length || 0}</span></div>
              {product.specifications?.length ? <div className="compact-pairs">{product.specifications.map((item, index) => <div className="compact-pair" key={`attr-${index}`}><span>{item.name}</span><strong>{item.value}</strong></div>)}</div> : <p className="muted-small">No specifications found. Confirm relevant details on the source page.</p>}
            </div>
            <div className="detail-block">
              <div className="detail-block-title"><span>Variations</span><span className="detail-count">{product.variations?.length || 0}</span></div>
              {product.variations?.length ? <div className="variation-chips">{product.variations.map((item, index) => <span className="variation-chip" key={`variation-${index}`}>{item}</span>)}</div> : <p className="muted-small">None detected. Double-check color, size, or quantity choices.</p>}
            </div>
          </div>

          {(product.package_contents?.length > 0 || product.usage_instructions?.length > 0 || product.warnings?.length > 0) && (
            <div className="source-facts-grid">
              {product.package_contents?.length > 0 && <FactList title="Package contents" items={product.package_contents} />}
              {product.usage_instructions?.length > 0 && <FactList title="Usage instructions" items={product.usage_instructions} />}
              {product.warnings?.length > 0 && <FactList title="Warnings & limitations" items={product.warnings} warning />}
            </div>
          )}
          {product.extraction_notes?.length > 0 && <div className="inline-review-note"><CircleAlert size={14} /><span>{product.extraction_notes.join(' ')}</span></div>}
          <div className="source-link-row"><span className="source-dot" /> Source product <a href={product.source_url} target="_blank" rel="noreferrer">Open AliExpress page <ExternalLink size={13} /></a></div>
        </section>

        <div className="review-footer-actions">
          <div className="trust-copy"><ShieldCheck size={15} /><span>Generated copy uses extracted facts only. You can review and edit it before exporting.</span></div>
          <button className="button button-primary generate-button" onClick={onGenerate} disabled={busy === 'generating'} type="button">
            {busy === 'generating' ? <Loader2 className="spin" size={16} /> : <WandSparkles size={16} />}
            {busy === 'generating' ? 'Writing your listing…' : 'Generate eBay copy'}<ArrowRight size={16} />
          </button>
          {!apiKeyConfigured && <button className="text-link api-key-link" type="button" onClick={onSettings}><KeyRound size={14} /> Add OpenAI key</button>}
        </div>
      </div>

      <aside className="image-column">
        <section className="panel image-panel">
          <div className="image-panel-heading"><div><h2>Product images</h2><p>Choose images for the listing.</p></div><span className="image-count-pill">{selectedImageCount} selected</span></div>
          {product.images?.length ? (
            <div className="image-grid">
              {product.images.map((image, index) => (
                <button className={`image-choice ${image.selected ? 'is-selected' : ''}`} key={`${image.url}-${index}`} onClick={() => toggleImage(index)} type="button" aria-pressed={image.selected}>
                  <img src={image.url} alt={image.alt || `Product image ${index + 1}`} loading="lazy" onError={(event) => { event.currentTarget.classList.add('image-failed'); }} />
                  <span className="image-check">{image.selected ? <Check size={14} /> : <span>{index + 1}</span>}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="images-empty"><ImageIcon size={22} /><strong>No images detected</strong><span>Images may not have loaded from the product page. You can still review the extracted copy.</span></div>
          )}
          <div className="image-panel-foot"><span>Click an image to include or exclude it.</span>{product.images?.length > 0 && selectedImageCount === 0 && <span className="image-warning">Select at least one.</span>}</div>
        </section>
        <div className="image-side-note"><div className="side-note-icon"><ShieldCheck size={16} /></div><p>Images are included using their original page URLs. Confirm they load in your eBay listing before publishing.</p></div>
      </aside>
    </div>
  );
}

function FactList({ title, items, warning = false }) {
  return <div className={`fact-list ${warning ? 'fact-warning' : ''}`}><strong>{title}</strong><ul>{items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}</ul></div>;
}

function ContentEditor({ content, setContent, busy, onPreview, onBack }) {
  const update = (key, value) => setContent({ ...content, [key]: value });
  const handleFeatures = (value) => update('features', value);
  return (
    <div className="editor-layout">
      <div className="editor-main">
        {content.review_flags?.length > 0 && (
          <div className="review-alert compact-review-alert"><div className="review-alert-icon"><CircleAlert size={17} /></div><div><strong>Seller review notes</strong><p>Resolve or confirm these items before publishing. They are for your review and won’t appear in the HTML listing.</p><ul>{content.review_flags.map((flag, index) => <li key={`flag-${index}`}>{flag}</li>)}</ul></div></div>
        )}
        <section className="panel editor-panel">
          <div className="panel-heading">
            <div className="panel-heading-icon gold"><WandSparkles size={17} /></div>
            <div><h2>Listing copy</h2><p>AI-assisted, fact-led copy. Make it yours before previewing.</p></div>
            <span className="ai-draft-tag"><Sparkles size={12} /> AI DRAFT</span>
          </div>
          <div className="editor-fields">
            <div className="field-label-row"><label htmlFor="listing-title" className="field-label">eBay title</label><span className={`character-count ${(content.title || '').length > 80 ? 'count-over' : ''}`}>{(content.title || '').length} / 80 characters</span></div>
            <input id="listing-title" className="text-input title-input" maxLength={80} value={content.title || ''} onChange={(event) => update('title', event.target.value)} placeholder="SEO-friendly eBay title" />
            <p className="field-help">Keep titles clear and searchable. eBay titles can be up to 80 characters.</p>
            <label htmlFor="listing-description" className="field-label description-label">Product description</label>
            <textarea id="listing-description" className="text-area listing-description" rows={8} maxLength={8000} value={content.description || ''} onChange={(event) => update('description', event.target.value)} placeholder="Describe the product accurately and clearly." />
          </div>
          <div className="editor-divider" />
          <FieldArray title="Key features & benefits" items={content.features} onChange={handleFeatures} placeholder="Add an accurate product feature" emptyLabel="No key features. Add the product benefits you can verify." helpText="Use concise points grounded in the extracted product details." maxLength={500} />
          <SpecificationEditor items={content.specifications} onChange={(value) => update('specifications', value)} />
          <FieldArray title="Package includes" items={content.package_contents} onChange={(value) => update('package_contents', value)} placeholder="Item included in the package" emptyLabel="No package contents listed." />
          <FieldArray title="Usage instructions" items={content.usage_instructions} onChange={(value) => update('usage_instructions', value)} placeholder="Usage or care instruction" emptyLabel="No instructions available." />
          <FieldArray title="Warnings & limitations" items={content.warnings} onChange={(value) => update('warnings', value)} placeholder="Important safety or limitation note" emptyLabel="No warnings were detected. Confirm this against the product page." helpText="Keep safety notes and limitations visible to buyers." />
        </section>
        <div className="editor-bottom-row">
          <button className="button button-secondary" type="button" onClick={onBack}><ArrowLeft size={15} /> Back to product</button>
          <button className="button button-primary" type="button" onClick={onPreview} disabled={busy === 'rendering' || !content.title.trim() || !content.description.trim()}>
            {busy === 'rendering' ? <Loader2 className="spin" size={16} /> : <Eye size={16} />}
            Preview HTML <ArrowRight size={15} />
          </button>
        </div>
      </div>
      <aside className="editor-aside">
        <div className="editor-aside-card fact-check-card"><div className="aside-card-icon"><ShieldCheck size={17} /></div><strong>Fact-check before you publish</strong><p>AI copy is a starting point. Check sizes, compatibility, materials, package contents, and every safety note against the original product.</p><div className="aside-check-line"><CheckCircle2 size={14} /> No invented specifications</div><div className="aside-check-line"><CheckCircle2 size={14} /> Seller review notes stay private</div></div>
        <div className="editor-aside-card"><div className="aside-card-label">YOUR STORE TEMPLATE</div><div className="template-mini"><div className="template-mini-head"><span>PRIMEPICK GOODS</span><i /></div><div className="template-mini-body"><span /><span /><span /></div><div className="template-mini-foot" /></div><p className="mini-caption">Your brand layout is applied in the preview.</p></div>
      </aside>
    </div>
  );
}

function PreviewPanel({ html, mode, setMode, busy, onRefresh, onCopy, onDownload, onSave, savedListingId, onEdit }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (await onCopy()) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    }
  };
  return (
    <div className="preview-page">
      <div className="preview-header-row">
        <div><div className="preview-kicker"><span className="preview-kicker-dot" /> READY FOR REVIEW</div><h2>Your branded HTML listing</h2><p>Preview it in isolation, inspect the source, then copy or download the complete HTML.</p></div>
        <button className="button button-secondary" onClick={onEdit} type="button"><FileText size={15} /> Edit listing copy</button>
      </div>
      <div className="preview-toolbar">
        <div className="preview-modes" role="tablist" aria-label="Preview mode">
          <button className={mode === 'preview' ? 'selected' : ''} type="button" onClick={() => setMode('preview')}><Eye size={15} /> Preview</button>
          <button className={mode === 'source' ? 'selected' : ''} type="button" onClick={() => setMode('source')}><Code2 size={15} /> HTML source</button>
        </div>
        <div className="preview-toolbar-actions">
          <button className="button button-quiet button-small" onClick={onRefresh} disabled={busy === 'rendering'} type="button"><RefreshCw className={busy === 'rendering' ? 'spin' : ''} size={14} /> Refresh</button>
          <span className="toolbar-divider" />
          <button className="button button-secondary button-small" onClick={copy} type="button">{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? 'Copied' : 'Copy HTML'}</button>
          <button className="button button-primary button-small" onClick={onDownload} type="button"><Download size={14} /> Download</button>
        </div>
      </div>
      <div className={`preview-canvas ${mode === 'source' ? 'source-canvas' : ''}`}>
        {mode === 'preview' ? (
          html ? <iframe className="listing-iframe" title="PrimePick Goods listing preview" sandbox="" referrerPolicy="no-referrer" srcDoc={html} /> : <div className="preview-loading"><Loader2 className="spin" size={22} /><span>{busy === 'rendering' ? 'Building your branded HTML…' : 'No HTML preview yet. Refresh to build it.'}</span></div>
        ) : (
          html ? <pre className="html-source"><code>{html}</code></pre> : <div className="preview-loading"><Loader2 className="spin" size={22} /><span>HTML source will appear after the listing is built.</span></div>
        )}
      </div>
      <div className="preview-footer-row">
        <div className="preview-security"><ShieldCheck size={15} /><span>Script-free HTML with inline styling and a table-based layout.</span></div>
        <div className="preview-save-actions">
          {savedListingId && <span className="saved-indicator"><CheckCircle2 size={14} /> Saved locally</span>}
          <button className={`button ${savedListingId ? 'button-secondary' : 'button-gold'}`} type="button" onClick={onSave} disabled={busy === 'saving'}>
            {busy === 'saving' ? <Loader2 className="spin" size={15} /> : savedListingId ? <Check size={15} /> : <Plus size={15} />}
            {busy === 'saving' ? 'Saving…' : savedListingId ? 'Saved to history' : 'Save to history'}
          </button>
        </div>
      </div>
    </div>
  );
}

function HistoryPage({ items, loading, reload, onOpen }) {
  return (
    <div className="page-content history-page">
      <div className="page-heading-row history-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> YOUR LOCAL LIBRARY</div><h1>Listing history</h1><p className="page-subtitle">Previously saved listings are stored on this computer.</p></div>
        <button className="button button-secondary" onClick={reload} type="button"><RefreshCw size={15} /> Refresh</button>
      </div>
      <div className="history-summary"><div className="history-summary-icon"><HistoryIcon size={18} /></div><div><strong>{items.length} saved {items.length === 1 ? 'listing' : 'listings'}</strong><span>Reopen a listing to edit, copy, or download its HTML.</span></div><span className="history-local"><LockKeyhole size={13} /> ON THIS DEVICE</span></div>
      {loading ? <div className="history-loading"><Loader2 className="spin" size={20} /> Loading saved listings…</div> : items.length === 0 ? (
        <div className="history-empty"><div className="history-empty-icon"><FileText size={23} /></div><h2>Your saved listings will appear here.</h2><p>When you save a finished listing, it will be ready to reopen and download from this library.</p></div>
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <button className="history-card" key={item.id} onClick={() => onOpen(item.id)} type="button">
              <div className="history-thumb">{item.thumbnail_url ? <img src={item.thumbnail_url} alt="" loading="lazy" /> : <ImageIcon size={22} />}</div>
              <div className="history-card-main"><div className="history-card-title">{item.title || 'Untitled listing'}</div><div className="history-card-meta"><span>{new Date(item.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</span><span className="meta-dot">·</span><span>eBay US listing</span></div></div>
              <span className="history-card-open">Open <ChevronRight size={15} /></span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SettingsPage({ settings, apiKey, setApiKey, model, setModel, clearSavedKey, setClearSavedKey, busy, onSave }) {
  return (
    <div className="page-content settings-page">
      <div className="page-heading-row">
        <div><div className="eyebrow"><span className="eyebrow-line" /> PREFERENCES</div><h1>Settings</h1><p className="page-subtitle">Connect OpenAI and choose how listing copy is generated.</p></div>
      </div>
      <div className="settings-layout">
        <form className="panel settings-panel" onSubmit={onSave}>
          <div className="panel-heading">
            <div className="panel-heading-icon navy"><KeyRound size={17} /></div>
            <div><h2>OpenAI connection</h2><p>Your API key is used only to generate listing copy.</p></div>
            <span className={`connection-tag ${settings.api_key_configured && !clearSavedKey ? 'connected' : ''}`}><span />{settings.api_key_configured && !clearSavedKey ? 'CONNECTED' : 'NOT CONNECTED'}</span>
          </div>
          <div className="settings-fields">
            <label className="field-label" htmlFor="openai-key">OpenAI API key</label>
            <div className="secure-input-wrap"><KeyRound size={16} /><input id="openai-key" type="password" autoComplete="new-password" value={apiKey} onChange={(event) => { setApiKey(event.target.value); setClearSavedKey(false); }} placeholder={settings.api_key_configured && !clearSavedKey ? 'Saved key is hidden — enter a new key to replace it' : 'Paste your OpenAI API key'} /></div>
            <p className="field-help">Your key is never shown again after saving. Create or manage it in your OpenAI account.</p>
            {settings.api_key_configured && <label className="clear-key-option"><input type="checkbox" checked={clearSavedKey} onChange={(event) => { setClearSavedKey(event.target.checked); if (event.target.checked) setApiKey(''); }} /><span>Remove the saved API key</span></label>}
            <div className="settings-divider" />
            <label className="field-label" htmlFor="model-name">Model</label>
            <input id="model-name" className="text-input" value={model} onChange={(event) => setModel(event.target.value)} placeholder="gpt-4o-mini" />
            <p className="field-help">Use a model that supports structured JSON output. The default is <code>gpt-4o-mini</code>.</p>
            <button className="button button-primary settings-save" disabled={busy === 'settings'} type="submit">{busy === 'settings' ? <Loader2 className="spin" size={16} /> : <Check size={16} />}{busy === 'settings' ? 'Saving…' : 'Save settings'}</button>
          </div>
        </form>
        <aside className="settings-aside">
          <div className="security-note"><div className="security-note-icon"><LockKeyhole size={17} /></div><strong>Stored locally</strong><p>On Windows, the key is saved in your Windows credential vault. On other systems, it is encrypted in your local app data folder. The app never includes a shared API key.</p><div className="security-note-rule" /><div className="security-note-foot"><ShieldCheck size={14} /> Your listing history is stored in a local SQLite database.</div></div>
          <div className="settings-help-card"><div className="settings-help-icon"><Sparkles size={16} /></div><div><strong>What does the AI do?</strong><p>It turns confirmed product details into a clear eBay US title, description, features, specifications, and package information. Missing details are flagged for your review.</p></div></div>
          <div className="settings-footnote"><span className="online-dot" /> {settings.key_storage || 'Local encrypted storage'}<br /><span className="settings-footnote-sub">An internet connection is needed for product pages and OpenAI.</span></div>
        </aside>
      </div>
    </div>
  );
}

export default App;
