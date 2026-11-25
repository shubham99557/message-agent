import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Plus,
  Edit2,
  CheckCircle2,
  XCircle,
  FileText,
  HelpCircle,
  Mail,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
  RefreshCw,
  Search
} from 'lucide-react';
import { api } from '../api/client';
import { ServiceCatalogueItem, ServiceCatalogueCreate } from '../types';

export const ServiceCatalogueView: React.FC = () => {
  const [services, setServices] = useState<ServiceCatalogueItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedService, setSelectedService] = useState<ServiceCatalogueItem | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showModal, setShowModal] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'claims' | 'templates' | 'questions'>('claims');

  // New Service Form State
  const [formData, setFormData] = useState<ServiceCatalogueCreate>({
    service_code: '',
    service_name: '',
    description: '',
    target_business_types: [],
    common_business_problems: [],
    approved_claims: [],
    disallowed_claims: [],
    discovery_questions: [],
    outreach_templates: {
      professional: { subject: '', body: '' },
      concise: { subject: '', body: '' }
    },
    is_active: true
  });

  const loadServices = async () => {
    setLoading(true);
    try {
      const data = await api.getServices();
      setServices(data || []);
      if (data && data.length > 0 && !selectedService) {
        setSelectedService(data[0]);
      }
    } catch (err) {
      console.error('Failed to load services:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadServices();
  }, []);

  const handleToggleActive = async (svc: ServiceCatalogueItem) => {
    try {
      const updated = await api.updateService(svc.id, { is_active: !svc.is_active });
      setServices(services.map(s => s.id === svc.id ? updated : s));
      if (selectedService?.id === svc.id) {
        setSelectedService(updated);
      }
    } catch (err) {
      console.error('Failed to toggle status:', err);
    }
  };

  const filteredServices = services.filter(s =>
    s.service_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.service_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-blue-600" />
            <h1 className="text-2xl font-bold text-slate-900">ActTrident Service Catalogue</h1>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Governs approved commercial capabilities, qualification heuristics, legal claims boundaries, and AI outreach templates.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadServices}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => {
              setFormData({
                service_code: `ACT-SRV-0${services.length + 1}`,
                service_name: '',
                description: '',
                target_business_types: ['software', 'it services'],
                common_business_problems: ['unmanaged endpoints', 'credential security'],
                approved_claims: ['Vetted workspace security controls', 'Compliant session isolation'],
                disallowed_claims: ['90-day evaluation without qualification', '100% hack-proof guarantee'],
                discovery_questions: ['How do developers access production resources?'],
                outreach_templates: {
                  professional: {
                    subject: 'Securing technical workflows at {company_name}',
                    body: 'Hi {contact_name},\n\nWe noticed {company_name}\'s work in {industry}...'
                  }
                },
                is_active: true
              });
              setShowModal(true);
            }}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Add Service
          </button>
        </div>
      </div>

      {/* Main Grid: Catalogue List & Details Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left List (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search services or code..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="space-y-3">
            {filteredServices.map(svc => {
              const isSelected = selectedService?.id === svc.id;
              return (
                <div
                  key={svc.id}
                  onClick={() => setSelectedService(svc)}
                  className={`p-4 rounded-xl border cursor-pointer transition ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50/50 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 text-xs font-semibold bg-slate-100 text-slate-800 rounded font-mono">
                          {svc.service_code}
                        </span>
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          svc.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {svc.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </div>
                      <h3 className="font-semibold text-slate-900 mt-2 text-base">{svc.service_name}</h3>
                      <p className="text-xs text-slate-500 line-clamp-2 mt-1">{svc.description}</p>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1">
                    {(svc.target_business_types || []).slice(0, 3).map((t, idx) => (
                      <span key={idx} className="text-[11px] px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
                        {t}
                      </span>
                    ))}
                    {(svc.target_business_types || []).length > 3 && (
                      <span className="text-[11px] text-slate-400 self-center">
                        +{(svc.target_business_types || []).length - 3} more
                      </span>
                    )}
                  </div>
                </div>
              );
            })}

            {filteredServices.length === 0 && !loading && (
              <div className="p-8 text-center bg-white rounded-xl border border-slate-200 text-slate-500 text-sm">
                No matching service catalogue items found.
              </div>
            )}
          </div>
        </div>

        {/* Right Detail Pane (7 cols) */}
        <div className="lg:col-span-7">
          {selectedService ? (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
              {/* Header */}
              <div className="flex justify-between items-start border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 text-xs font-bold bg-blue-100 text-blue-800 rounded font-mono">
                      {selectedService.service_code}
                    </span>
                    <button
                      onClick={() => handleToggleActive(selectedService)}
                      className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"
                    >
                      {selectedService.is_active ? (
                        <>
                          <ToggleRight className="w-5 h-5 text-emerald-600" />
                          <span className="text-emerald-700 font-medium">Active</span>
                        </>
                      ) : (
                        <>
                          <ToggleLeft className="w-5 h-5 text-slate-400" />
                          <span>Disabled</span>
                        </>
                      )}
                    </button>
                  </div>
                  <h2 className="text-xl font-bold text-slate-900 mt-2">{selectedService.service_name}</h2>
                  <p className="text-sm text-slate-600 mt-1 leading-relaxed">{selectedService.description}</p>
                </div>
              </div>

              {/* Target Profiles & Pain Points */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-lg">
                <div>
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Target Business Sectors</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {(selectedService.target_business_types || []).map((t, idx) => (
                      <span key={idx} className="text-xs bg-white border border-slate-200 text-slate-700 px-2 py-0.5 rounded">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Key Pain Points Solved</h4>
                  <ul className="text-xs text-slate-600 space-y-1 list-disc list-inside">
                    {(selectedService.common_business_problems || []).map((p, idx) => (
                      <li key={idx} className="line-clamp-1">{p}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Sub-Tabs: Claims | Templates | Discovery Questions */}
              <div>
                <div className="flex border-b border-slate-200 gap-4">
                  <button
                    onClick={() => setActiveTab('claims')}
                    className={`pb-2 text-sm font-medium border-b-2 transition ${
                      activeTab === 'claims'
                        ? 'border-blue-600 text-blue-600 font-semibold'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Claims Guardrails ({selectedService.approved_claims?.length || 0})
                  </button>
                  <button
                    onClick={() => setActiveTab('templates')}
                    className={`pb-2 text-sm font-medium border-b-2 transition ${
                      activeTab === 'templates'
                        ? 'border-blue-600 text-blue-600 font-semibold'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Outreach Angle Templates
                  </button>
                  <button
                    onClick={() => setActiveTab('questions')}
                    className={`pb-2 text-sm font-medium border-b-2 transition ${
                      activeTab === 'questions'
                        ? 'border-blue-600 text-blue-600 font-semibold'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Discovery Questions ({selectedService.discovery_questions?.length || 0})
                  </button>
                </div>

                {/* Tab 1: Claims */}
                {activeTab === 'claims' && (
                  <div className="mt-4 space-y-4">
                    <div>
                      <div className="flex items-center gap-1.5 text-emerald-700 text-sm font-semibold mb-2">
                        <CheckCircle2 className="w-4 h-4" />
                        Approved Compliant Claims (Safe for AI Outreach)
                      </div>
                      <div className="space-y-1.5">
                        {(selectedService.approved_claims || []).map((claim, idx) => (
                          <div key={idx} className="p-2.5 bg-emerald-50/70 border border-emerald-200 rounded text-xs text-emerald-900 flex items-start gap-2">
                            <span className="text-emerald-500 font-bold">✓</span>
                            <span>{claim}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center gap-1.5 text-rose-700 text-sm font-semibold mb-2">
                        <XCircle className="w-4 h-4" />
                        Disallowed Claims (Blocked by Central Claims Engine)
                      </div>
                      <div className="space-y-1.5">
                        {(selectedService.disallowed_claims || []).map((claim, idx) => (
                          <div key={idx} className="p-2.5 bg-rose-50/70 border border-rose-200 rounded text-xs text-rose-900 flex items-start gap-2">
                            <span className="text-rose-500 font-bold">✕</span>
                            <span>{claim}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab 2: Templates */}
                {activeTab === 'templates' && (
                  <div className="mt-4 space-y-4">
                    {selectedService.outreach_templates && Object.keys(selectedService.outreach_templates).length > 0 ? (
                      Object.entries(selectedService.outreach_templates).map(([styleKey, tpl]) => (
                        <div key={styleKey} className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-700">{styleKey} Style</span>
                            <span className="text-[11px] text-slate-400 font-mono">Variables: company_name, contact_name, city, industry</span>
                          </div>
                          <div className="text-xs text-slate-800 font-medium mb-1">Subject: {tpl.subject}</div>
                          <pre className="text-xs text-slate-600 bg-white p-3 rounded border border-slate-200 whitespace-pre-wrap font-sans">
                            {tpl.body}
                          </pre>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-slate-500 italic p-4 text-center">No templates defined for this service.</p>
                    )}
                  </div>
                )}

                {/* Tab 3: Discovery Questions */}
                {activeTab === 'questions' && (
                  <div className="mt-4 space-y-2">
                    {(selectedService.discovery_questions || []).map((q, idx) => (
                      <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-800 flex items-start gap-2">
                        <HelpCircle className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                        <span>{q}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center bg-white rounded-xl border border-slate-200 text-slate-400">
              Select a service from the catalogue to view details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
