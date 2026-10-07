'use client';

import { LibraryItem } from '@/lib/api/library';
import { AnalysisStatus, getAnalysis, runAnalysis, translateAnalysis, getAnalysisContent } from '@/lib/api/analysis';
import { useLibraryStore } from '@/lib/store/library';
import { X, Sparkles, Copy, Download, RotateCcw, Check } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface AnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  item?: LibraryItem;
}

type Tab = 'summary' | 'transcript' | 'subtitles';

export function AnalysisModal({ isOpen, onClose, item }: AnalysisModalProps) {
  const { addToast } = useLibraryStore();
  const [analysis, setAnalysis] = useState<AnalysisStatus | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('summary');
  const [isRunning, setIsRunning] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translateLang, setTranslateLang] = useState('es');
  const [copied, setCopied] = useState(false);
  const [contentCache, setContentCache] = useState<Record<string, string>>({});
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const reset = () => {
    setAnalysis(null);
    setActiveTab('summary');
    setIsRunning(false);
    setIsTranslating(false);
    setTranslateLang('es');
    setCopied(false);
    setContentCache({});
    if (pollRef.current) clearInterval(pollRef.current);
  };

  useEffect(() => {
    if (isOpen) {
      reset();
      if (item?.analysis_status === 'processing' || item?.analysis_status === 'completed') {
        fetchAnalysis();
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, item?.id]);

  const fetchAnalysis = async () => {
    if (!item) return;
    try {
      const data = await getAnalysis(item.id);
      setAnalysis(data);
      if (data.status === 'completed') {
        if (pollRef.current) clearInterval(pollRef.current);
      } else if (data.status === 'processing') {
        if (!pollRef.current) {
          pollRef.current = setInterval(fetchAnalysis, 3000);
        }
      }
    } catch {
      console.error();
    }
  };

  const handleRun = async () => {
    if (!item) return;
    setIsRunning(true);
    try {
      await runAnalysis(item.id);
      addToast('AI Analysis started', 'info');
      fetchAnalysis();
      if (!pollRef.current) {
        pollRef.current = setInterval(fetchAnalysis, 3000);
      }
    } catch {
      addToast('Failed to start analysis', 'error');
      setIsRunning(false);
    }
  };

  const handleRetry = async () => {
    if (!item) return;
    setIsRunning(true);
    try {
      await runAnalysis(item.id);
      addToast('Retrying analysis...', 'info');
      fetchAnalysis();
      if (!pollRef.current) {
        pollRef.current = setInterval(fetchAnalysis, 3000);
      }
    } catch {
      addToast('Failed to retry analysis', 'error');
      setIsRunning(false);
    }
  };

  const handleTranslate = async () => {
    if (!item) return;
    setIsTranslating(true);
    try {
      await translateAnalysis(item.id, translateLang);
      addToast(`Translation to ${translateLang} started`, 'info');
      setTimeout(() => fetchAnalysis(), 1000);
    } catch {
      addToast('Failed to request translation', 'error');
    } finally {
      setIsTranslating(false);
    }
  };

  const loadContent = async (kind: 'transcript' | 'summary' | 'srt', lang?: string) => {
    if (!item) return '';
    const cacheKey = lang ? `${kind}-${lang}` : kind;
    if (contentCache[cacheKey]) return contentCache[cacheKey];
    try {
      const data = await getAnalysisContent(item.id, lang ? `${kind}/${lang}` : kind);
      setContentCache((prev) => ({ ...prev, [cacheKey]: data.content }));
      return data.content;
    } catch {
      return '';
    }
  };

  const handleCopyTranscript = async () => {
    if (!item) return;
    const text = await loadContent('transcript');
    if (!text) {
      addToast('Transcript not available', 'error');
      return;
    }
    await navigator.clipboard.writeText(text);
    setCopied(true);
    addToast('Transcript copied to clipboard', 'success');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadTranscript = async () => {
    if (!item) return;
    const text = await loadContent('transcript');
    if (!text) {
      addToast('Transcript not available', 'error');
      return;
    }
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${item.title.replace(/[^a-z0-9]/gi, '_')}_transcript.txt`;
    a.click();
    URL.revokeObjectURL(url);
    addToast('Transcript downloaded', 'success');
  };

  const handleDownloadSrt = async (lang: string) => {
    if (!item) return;
    const content = await loadContent('srt', lang);
    if (!content) {
      addToast('Subtitle not available', 'error');
      return;
    }
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${item.title.replace(/[^a-z0-9]/gi, '_')}_${lang}.srt`;
    a.click();
    URL.revokeObjectURL(url);
    addToast('Subtitle downloaded', 'success');
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: 'summary', label: 'Summary' },
    { key: 'transcript', label: 'Transcript' },
    { key: 'subtitles', label: 'Subtitles' },
  ];

  const isProcessing = analysis?.status === 'processing';
  const isCompleted = analysis?.status === 'completed';
  const isFailed = analysis?.status === 'failed';
  const isNone = !analysis || analysis.status === 'none';

  return (
    <AnimatePresence>
      {isOpen && item && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="glass-card rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-6 border-b border-border">
              <div className="flex items-center gap-3 min-w-0">
                <Sparkles className="w-5 h-5 text-accent-secondary shrink-0" />
                <h2 className="text-lg font-bold text-text-primary truncate">{item.title}</h2>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {isProcessing && (
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-accent-primary/20 text-accent-primary animate-pulse">
                    Analyzing...
                  </span>
                )}
                {isCompleted && analysis.language && (
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-status-success/20 text-status-success">
                    {analysis.language}
                  </span>
                )}
                {isFailed && (
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-status-error/20 text-status-error">
                    Failed
                  </span>
                )}
                <button
                  onClick={onClose}
                  className="p-2 rounded-full hover:bg-bg-tertiary text-text-secondary transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {isNone && (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
                <Sparkles className="w-16 h-16 text-accent-secondary mb-4" />
                <p className="text-text-secondary mb-6">No AI analysis yet. Run analysis to get a summary, transcript, and subtitles.</p>
                <button
                  onClick={handleRun}
                  disabled={isRunning}
                  className="px-6 py-3 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  {isRunning ? 'Starting...' : 'Run AI Analysis'}
                </button>
              </div>
            )}

            {isFailed && (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
                <p className="text-status-error mb-2">Analysis failed</p>
                {analysis.error && <p className="text-text-secondary text-sm mb-6 max-w-md">{analysis.error}</p>}
                <button
                  onClick={handleRetry}
                  disabled={isRunning}
                  className="px-6 py-3 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  Retry Analysis
                </button>
              </div>
            )}

            {(isProcessing || isCompleted) && (
              <>
                <div className="flex border-b border-border">
                  {tabs.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`flex-1 py-3 text-sm font-medium transition-colors relative ${
                        activeTab === tab.key ? 'text-accent-primary' : 'text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {tab.label}
                      {activeTab === tab.key && (
                        <motion.div
                          layoutId="activeTab"
                          className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-accent-primary to-accent-secondary"
                        />
                      )}
                    </button>
                  ))}
                </div>

                <div className="flex-1 overflow-y-auto p-6">
                  {activeTab === 'summary' && (
                    <div className="space-y-4">
                      {analysis.summary_text ? (
                        <>
                          <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border">
                            <p className="text-text-primary text-sm leading-relaxed whitespace-pre-wrap">{analysis.summary_text}</p>
                          </div>
                          {analysis.keywords && analysis.keywords.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {analysis.keywords.map((keyword) => (
                                <span
                                  key={keyword}
                                  className="px-3 py-1 rounded-lg text-xs font-medium bg-gradient-to-r from-accent-primary/20 to-accent-secondary/20 text-accent-primary border border-accent-primary/30"
                                >
                                  {keyword}
                                </span>
                              ))}
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="text-text-muted text-center py-8">Summary not available yet</p>
                      )}
                    </div>
                  )}

                  {activeTab === 'transcript' && (
                    <div className="space-y-4">
                      {analysis.transcript_text ? (
                        <>
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={handleCopyTranscript}
                              className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-elevated text-text-secondary hover:text-text-primary transition-colors flex items-center gap-2 text-xs"
                            >
                              {copied ? <Check className="w-4 h-4 text-status-success" /> : <Copy className="w-4 h-4" />}
                              {copied ? 'Copied' : 'Copy'}
                            </button>
                            <button
                              onClick={handleDownloadTranscript}
                              className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-elevated text-text-secondary hover:text-text-primary transition-colors flex items-center gap-2 text-xs"
                            >
                              <Download className="w-4 h-4" />
                              .txt
                            </button>
                          </div>
                          <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border max-h-[50vh] overflow-y-auto">
                            <pre className="text-xs text-text-primary font-mono whitespace-pre-wrap leading-relaxed">
                              {formatTranscript(analysis.transcript_text)}
                            </pre>
                          </div>
                        </>
                      ) : (
                        <p className="text-text-muted text-center py-8">Transcript not available yet</p>
                      )}
                    </div>
                  )}

                  {activeTab === 'subtitles' && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <p className="text-text-primary font-medium text-sm">Original</p>
                        <button
                          onClick={() => handleDownloadSrt('original')}
                          className="px-3 py-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-elevated text-text-secondary hover:text-text-primary transition-colors text-xs flex items-center gap-2"
                        >
                          <Download className="w-3 h-3" />
                          Download SRT
                        </button>
                      </div>

                      {analysis.translated && Object.keys(analysis.translated).length > 0 && (
                        <div className="space-y-2">
                          <p className="text-text-secondary text-xs font-medium uppercase tracking-wider">Translated</p>
                          {Object.entries(analysis.translated).map(([lang]) => (
                            <div key={lang} className="flex items-center justify-between p-3 rounded-lg bg-bg-tertiary/50 border border-border">
                              <span className="text-text-primary text-sm font-medium uppercase">{lang}</span>
                              <button
                                onClick={() => handleDownloadSrt(lang)}
                                className="px-3 py-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-elevated text-text-secondary hover:text-text-primary transition-colors text-xs flex items-center gap-2"
                              >
                                <Download className="w-3 h-3" />
                                Download SRT
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="pt-4 border-t border-border">
                        <p className="text-text-secondary text-xs font-medium uppercase tracking-wider mb-3">Translate to...</p>
                        <div className="flex gap-2">
                          <select
                            value={translateLang}
                            onChange={(e) => setTranslateLang(e.target.value)}
                            className="flex-1 px-3 py-2 rounded-lg bg-bg-tertiary border border-border text-text-primary text-sm focus:outline-none focus:border-accent-primary"
                          >
                            {['en', 'ur', 'ar', 'hi', 'es', 'fr', 'de', 'zh', 'ja', 'ko'].map((l) => (
                              <option key={l} value={l}>{l.toUpperCase()}</option>
                            ))}
                          </select>
                          <button
                            onClick={handleTranslate}
                            disabled={isTranslating}
                            className="px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
                          >
                            {isTranslating ? 'Translating...' : 'Translate'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function formatTranscript(text: string): string {
  const lines = text.split('\n');
  return lines
    .map((line) => {
      const match = line.match(/\[(\d{2}:\d{2})\](.*)/);
      if (match) {
        return `[${match[1]}] ${match[2].trim()}`;
      }
      return line;
    })
    .join('\n');
}

