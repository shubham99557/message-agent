import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ReplyItem } from '../types';
import {
  Inbox,
  MessageSquare,
  Sparkles,
  CheckCircle2,
  Clock,
  Send,
  AlertTriangle,
  RefreshCw,
  Plus
} from 'lucide-react';

export const InboxView: React.FC = () => {
  const [replies, setReplies] = useState<ReplyItem[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [loading, setLoading] = useState(true);
  const [selectedReply, setSelectedReply] = useState<ReplyItem | null>(null);
  const [editedResponse, setEditedResponse] = useState('');
  const [showSimulateModal, setShowSimulateModal] = useState(false);
  const [simText, setSimText] = useState('We are very interested in the 90-day evaluation. Can we schedule a demo this Thursday?');
  const [simSender, setSimSender] = useState('director@northbengaltech.example.com');

  const loadInbox = async () => {
    setLoading(true);
    try {
      const data = await api.getInbox(categoryFilter === 'All' ? undefined : categoryFilter);
      setReplies(data.items);
      setCategories(data.available_categories);
      if (data.items.length > 0 && !selectedReply) {
        setSelectedReply(data.items[0]);
        setEditedResponse(data.items[0].suggested_response || '');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInbox();
  }, [categoryFilter]);

  const handleSelectReply = (r: ReplyItem) => {
    setSelectedReply(r);
    setEditedResponse(r.suggested_response || '');
  };

  const handleApproveSuggested = async () => {
    if (!selectedReply) return;
    try {
      const updated = await api.approveReplyResponse(selectedReply.id, editedResponse);
      setSelectedReply(updated);
      alert('Negotiation response approved! System logged human sign-off.');
      loadInbox();
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    }
  };

  const handleSimulateInbound = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const data = await api.ingestInboundReply({
        channel: 'email',
        sender_identifier: simSender,
        recipient_identifier: 'outreach@acttrident.ai',
        subject: 'Re: ActTrident Evaluation',
        message_body: simText
      });
      setShowSimulateModal(false);
      loadInbox();
      setSelectedReply(data);
      setEditedResponse(data.suggested_response || '');
    } catch (err: any) {
      alert(`Simulation error: ${err.message}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">Inbound Inbox & 10-Class AI Reply Classifier</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Categorizes incoming responses and generates response drafts. Negotiations require human sign-off.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowSimulateModal(true)}
            className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center space-x-1"
          >
            <Plus className="w-3.5 h-3.5 text-cobalt-400" />
            <span>Simulate Inbound Reply</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-2 text-xs">
        <button
          onClick={() => setCategoryFilter('All')}
          className={`px-3 py-1.5 rounded-full font-mono text-[11px] whitespace-nowrap transition-colors ${
            categoryFilter === 'All' ? 'bg-cobalt-600 text-white' : 'bg-cobalt-900 text-slate-400 hover:text-slate-200 border border-cobalt-800'
          }`}
        >
          All Replies ({replies.length})
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={`px-3 py-1.5 rounded-full font-mono text-[11px] whitespace-nowrap transition-colors ${
              categoryFilter === cat ? 'bg-cobalt-600 text-white' : 'bg-cobalt-900 text-slate-400 hover:text-slate-200 border border-cobalt-800'
            }`}
          >
            {cat.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* 2-Pane Inbox Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Pane: Inbound List */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden flex flex-col max-h-[600px]">
          <div className="p-3 border-b border-cobalt-800 text-xs font-semibold text-slate-200">
            Messages ({replies.length})
          </div>
          <div className="divide-y divide-cobalt-800/60 overflow-y-auto">
            {replies.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No replies matching filter.</div>
            ) : (
              replies.map((r) => {
                const isSelected = selectedReply?.id === r.id;
                return (
                  <button
                    key={r.id}
                    onClick={() => handleSelectReply(r)}
                    className={`w-full text-left p-3.5 transition-colors ${
                      isSelected ? 'bg-cobalt-850 border-l-2 border-cobalt-500' : 'hover:bg-cobalt-900/50'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-slate-100 truncate">{r.company_name || r.sender_identifier}</span>
                      <span className="text-[10px] font-mono text-slate-500">
                        {new Date(r.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-300 font-mono truncate mb-1">{r.subject || 'No Subject'}</div>
                    <div className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-2">{r.message_body}</div>
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded border ${
                          r.classification === 'interested' || r.classification === 'requests_demonstration'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : r.classification === 'unsubscribe' || r.classification === 'not_interested'
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                            : 'bg-cobalt-950 text-cobalt-300 border-cobalt-800'
                        }`}
                      >
                        {r.classification.replace(/_/g, ' ')}
                      </span>
                      {r.is_negotiation && !r.human_approved && (
                        <span className="text-[9px] font-mono text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded">
                          Requires Sign-off
                        </span>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Pane: Detail & AI Suggested Response */}
        <div className="lg:col-span-2 bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 flex flex-col space-y-4">
          {selectedReply ? (
            <>
              {/* Message Header */}
              <div className="border-b border-cobalt-800 pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-slate-100">{selectedReply.subject || 'Conversation Discussion'}</h3>
                  <div className="text-xs text-slate-400 mt-0.5">
                    From: <span className="font-mono text-slate-300">{selectedReply.sender_identifier}</span> • Channel: <span className="uppercase font-mono">{selectedReply.channel}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-cobalt-300">
                    Confidence: {(selectedReply.classification_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Message Content */}
              <div className="bg-cobalt-950 p-4 rounded border border-cobalt-800 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                {selectedReply.message_body}
              </div>

              {/* AI Classification Rationale */}
              <div className="text-xs bg-cobalt-950/60 p-3 rounded border border-cobalt-800 text-slate-300 space-y-1">
                <span className="font-semibold text-slate-200">AI Classification: </span>
                <span className="font-mono text-cobalt-400 capitalize">{selectedReply.classification.replace(/_/g, ' ')}</span>
                <p className="text-[11px] text-slate-400">{selectedReply.classification_reason}</p>
              </div>

              {/* Suggested AI Response Form */}
              <div className="space-y-2 pt-2 border-t border-cobalt-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-200 flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-cobalt-400" />
                    <span>Suggested Response (Human In The Loop)</span>
                  </span>
                  {selectedReply.human_approved ? (
                    <span className="text-[10px] font-mono text-emerald-400 flex items-center space-x-1">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Approved by User</span>
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono text-amber-400 flex items-center space-x-1">
                      <AlertTriangle className="w-3 h-3" />
                      <span>Negotiation Sign-off Required</span>
                    </span>
                  )}
                </div>

                <textarea
                  rows={6}
                  value={editedResponse}
                  onChange={(e) => setEditedResponse(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded p-3 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-sans leading-relaxed"
                ></textarea>

                <div className="flex items-center justify-between pt-2">
                  <div className="text-[11px] text-slate-400">
                    Policy: Do not send automated replies to negotiations without human approval.
                  </div>
                  <button
                    onClick={handleApproveSuggested}
                    className="px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1"
                  >
                    <span>Approve & Record Response</span>
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="p-16 text-center text-xs text-slate-400">Select a message on the left to inspect.</div>
          )}
        </div>
      </div>

      {/* Simulate Modal */}
      {showSimulateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-md space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Simulate Inbound Prospect Reply</h3>
              <button onClick={() => setShowSimulateModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleSimulateInbound} className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Sender Email</label>
                <input
                  type="email"
                  value={simSender}
                  onChange={(e) => setSimSender(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Reply Text (Test 10 Classes)</label>
                <textarea
                  rows={5}
                  value={simText}
                  onChange={(e) => setSimText(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded p-2.5 text-xs text-slate-200"
                  required
                ></textarea>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowSimulateModal(false)}
                  className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium"
                >
                  Classify & Ingest
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
