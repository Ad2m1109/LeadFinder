"use client";

import React, { useState, useEffect, useRef } from "react";

interface Lead {
  name: string;
  phone: string;
  website: string;
  rating: number;
  reviews: number;
  address: string;
  email?: string;
  instagram?: string;
  facebook?: string;
  seo_score?: number;
  screenshot?: string;
  seo_issues?: string;
}

interface ScraperStatus {
  status: "idle" | "running" | "completed" | "failed";
  query: string;
  leads_found: number;
  current_lead: Lead | null;
  error: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Dashboard() {
  // Search state
  const [category, setCategory] = useState("Restaurant");
  const [city, setCity] = useState("Tirana");
  const [country, setCountry] = useState("Albania");
  const [maxResults, setMaxResults] = useState(20);

  // App states
  const [leads, setLeads] = useState<Lead[]>([]);
  const [status, setStatus] = useState<ScraperStatus>({
    status: "idle",
    query: "",
    leads_found: 0,
    current_lead: null,
    error: null,
  });
  const [searchFilter, setSearchFilter] = useState("");
  const [isLoadingLeads, setIsLoadingLeads] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch all leads currently stored
  const fetchLeads = async () => {
    try {
      setIsLoadingLeads(true);
      const res = await fetch(`${API_BASE}/api/leads`);
      if (res.ok) {
        const data = await res.json();
        setLeads(data.leads || []);
      }
    } catch (err) {
      console.error("Failed to fetch leads:", err);
    } finally {
      setIsLoadingLeads(false);
    }
  };

  // Poll scraper status
  const pollStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      if (res.ok) {
        const data: ScraperStatus = await res.json();
        setStatus(data);

        if (data.status === "running") {
          // If running, we should periodically refresh leads to show live additions
          const leadsRes = await fetch(`${API_BASE}/api/leads`);
          if (leadsRes.ok) {
            const leadsData = await leadsRes.json();
            setLeads(leadsData.leads || []);
          }
        } else {
          // Scraper finished, stopped, or failed - stop polling
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          // Fetch final leads list
          fetchLeads();
        }
      }
    } catch (err) {
      console.error("Error polling scraper status:", err);
    }
  };

  // Start polling if status is running
  useEffect(() => {
    setMounted(true);
    // Initial fetch
    fetchLeads();
    pollStatus();

    // Check status immediately
    const checkInitialStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (res.ok) {
          const data: ScraperStatus = await res.json();
          setStatus(data);
          if (data.status === "running") {
            startPolling();
          }
        }
      } catch (err) {
        console.error(err);
      }
    };
    checkInitialStatus();

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const startPolling = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(pollStatus, 1500);
  };

  // Handle start scraping form submit
  const handleStartScrape = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const res = await fetch(`${API_BASE}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category,
          city,
          country,
          max_results: maxResults,
        }),
      });

      if (res.ok) {
        setStatus((prev) => ({
          ...prev,
          status: "running",
          query: `${category} in ${city}, ${country}`,
          leads_found: 0,
          current_lead: null,
          error: null,
        }));
        startPolling();
      } else {
        const errData = await res.json();
        setErrorMessage(errData.detail || "Failed to start scraper.");
      }
    } catch (err) {
      setErrorMessage("Could not connect to backend server. Is it running?");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle database clear
  const handleClearDatabase = async () => {
    if (!confirm("Are you sure you want to clear all leads? This will delete the local file.")) return;

    try {
      const res = await fetch(`${API_BASE}/api/clear`, { method: "POST" });
      if (res.ok) {
        setLeads([]);
        setStatus((prev) => ({ ...prev, status: "idle", current_lead: null, leads_found: 0 }));
      } else {
        const errData = await res.json();
        alert(errData.detail || "Failed to clear database.");
      }
    } catch (err) {
      alert("Error contacting backend to clear database.");
    }
  };

  // Filter leads based on search box
  const filteredLeads = leads.filter((lead) => {
    const term = searchFilter.toLowerCase();
    return (
      lead.name.toLowerCase().includes(term) ||
      lead.phone.toLowerCase().includes(term) ||
      lead.website.toLowerCase().includes(term) ||
      lead.address.toLowerCase().includes(term) ||
      (lead.email && lead.email.toLowerCase().includes(term)) ||
      (lead.instagram && lead.instagram.toLowerCase().includes(term)) ||
      (lead.facebook && lead.facebook.toLowerCase().includes(term))
    );
  });

  // Export leads to CSV
  const handleDownloadCSV = () => {
    if (leads.length === 0) return;

    const headers = ["Name", "Phone", "Website", "Rating", "Reviews", "Address", "Email", "Instagram", "Facebook", "SEO Score", "SEO Issues"];
    const csvRows = [
      headers.join(","),
      ...leads.map((lead) =>
        [
          `"${lead.name.replace(/"/g, '""')}"`,
          `"${lead.phone.replace(/"/g, '""')}"`,
          `"${lead.website.replace(/"/g, '""')}"`,
          lead.rating,
          lead.reviews,
          `"${lead.address.replace(/"/g, '""')}"`,
          `"${(lead.email || "").replace(/"/g, '""')}"`,
          `"${(lead.instagram || "").replace(/"/g, '""')}"`,
          `"${(lead.facebook || "").replace(/"/g, '""')}"`,
          lead.seo_score ?? 0,
          `"${(lead.seo_issues || "").replace(/"/g, '""')}"`
        ].join(",")
      ),
    ];

    const csvContent = "data:text/csv;charset=utf-8," + csvRows.join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `leads_${category.toLowerCase()}_${city.toLowerCase()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (!mounted) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center">
        <svg className="animate-spin h-10 w-10 text-indigo-500 mb-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <p className="text-zinc-400 text-sm font-medium animate-pulse">Loading LeadFinder...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans selection:bg-indigo-500 selection:text-white pb-12">
      {/* Background Gradients */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full filter blur-3xl -z-10 animate-pulse duration-10000" />
      <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full filter blur-3xl -z-10 animate-pulse duration-7000" />

      {/* Navigation Header */}
      <header className="border-b border-zinc-800/80 bg-zinc-900/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <div>
              <span className="font-semibold text-lg bg-gradient-to-r from-indigo-200 to-zinc-100 bg-clip-text text-transparent">
                LeadFinder
              </span>
              <span className="text-[10px] text-zinc-500 block -mt-1 font-mono">v1.0.0 (MVP)</span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {status.status === "running" && (
              <span className="flex h-3 w-3 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
            )}
            <span className="text-sm font-medium text-zinc-400">
              Status:{" "}
              <span
                className={`font-semibold capitalize ${
                  status.status === "running"
                    ? "text-emerald-400 animate-pulse"
                    : status.status === "completed"
                    ? "text-indigo-400"
                    : status.status === "failed"
                    ? "text-rose-400"
                    : "text-zinc-500"
                }`}
              >
                {status.status}
              </span>
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Form Card */}
        <div className="lg:col-span-1">
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-6 backdrop-blur-xl shadow-xl">
            <h2 className="text-xl font-semibold text-zinc-100 mb-6 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Search Configuration
            </h2>

            <form onSubmit={handleStartScrape} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">Category</label>
                <input
                  type="text"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="e.g. Restaurant, Dentist, Gym"
                  required
                  disabled={status.status === "running"}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">City</label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="e.g. Tirana"
                    required
                    disabled={status.status === "running"}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">Country</label>
                  <input
                    type="text"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    placeholder="e.g. Albania"
                    required
                    disabled={status.status === "running"}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">Max Results Limit</label>
                <input
                  type="number"
                  min="1"
                  max="200"
                  value={maxResults}
                  onChange={(e) => setMaxResults(parseInt(e.target.value) || 10)}
                  required
                  disabled={status.status === "running"}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
                />
              </div>

              {errorMessage && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs font-medium">
                  {errorMessage}
                </div>
              )}

              <button
                type="submit"
                disabled={status.status === "running" || isSubmitting}
                className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium py-3 px-4 rounded-xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 transition flex items-center justify-center gap-2 mt-4 disabled:from-zinc-800 disabled:to-zinc-800 disabled:text-zinc-500 disabled:shadow-none disabled:cursor-not-allowed"
              >
                {status.status === "running" ? (
                  <>
                    <svg className="animate-spin h-5 w-5 text-zinc-500" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Scraping Google Maps...
                  </>
                ) : isSubmitting ? (
                  "Initializing..."
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Start Scraping Leads
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Status and Realtime Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Scraping Status Card */}
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-6 backdrop-blur-xl shadow-xl flex flex-col justify-between min-h-[300px]">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  Live Scraper Status
                </h2>
                {status.status === "running" && (
                  <span className="px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-full animate-pulse">
                    Active
                  </span>
                )}
              </div>

              {status.status === "idle" && (
                <div className="text-center py-12">
                  <p className="text-zinc-400 text-base">No active scrapers.</p>
                  <p className="text-xs text-zinc-600 mt-1">Configure search settings on the left to start finding leads.</p>
                </div>
              )}

              {status.status === "failed" && (
                <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-sm mb-4">
                  <span className="font-semibold block mb-1">Scraper Failed</span>
                  {status.error || "An unknown error occurred during execution."}
                </div>
              )}

              {status.status !== "idle" && (
                <div className="grid grid-cols-2 gap-6 mb-6">
                  <div className="bg-zinc-950/40 border border-zinc-800/50 rounded-xl p-4">
                    <span className="text-xs font-semibold text-zinc-500 block uppercase tracking-wider">Search Query</span>
                    <span className="text-zinc-200 font-medium text-sm mt-1 block truncate">
                      {status.query || "N/A"}
                    </span>
                  </div>
                  <div className="bg-zinc-950/40 border border-zinc-800/50 rounded-xl p-4">
                    <span className="text-xs font-semibold text-zinc-500 block uppercase tracking-wider">Leads Found</span>
                    <span className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent mt-1 block">
                      {status.leads_found}
                    </span>
                  </div>
                </div>
              )}

              {status.status === "running" && status.current_lead && (
                <div className="bg-zinc-950/60 border border-zinc-800/60 rounded-xl p-4 animate-fade-in">
                  <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest block mb-2">
                    ⚡ Currently Scraping:
                  </span>
                  <div className="space-y-1.5">
                    <h3 className="font-semibold text-zinc-200">{status.current_lead.name}</h3>
                    <p className="text-xs text-zinc-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" />
                      Address: {status.current_lead.address || "N/A"}
                    </p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs font-medium text-zinc-400 pt-1">
                      <span>Phone: {status.current_lead.phone || "None"}</span>
                      <span>Website: {status.current_lead.website || "None"}</span>
                      <span className="text-amber-400">★ {status.current_lead.rating || "N/A"} ({status.current_lead.reviews || 0})</span>
                      {status.current_lead.email && <span className="text-indigo-400 flex items-center gap-0.5">📧 {status.current_lead.email}</span>}
                      {status.current_lead.instagram && <span className="text-pink-400 flex items-center gap-0.5">📸 Instagram</span>}
                      {status.current_lead.facebook && <span className="text-blue-400 flex items-center gap-0.5">👤 Facebook</span>}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {status.status === "completed" && (
              <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 rounded-xl text-sm flex items-center justify-between mt-auto">
                <div>
                  <span className="font-semibold block mb-0.5">Scraping Complete!</span>
                  Successfully processed your request and updated Google Sheets.
                </div>
                <button
                  onClick={handleDownloadCSV}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2 px-4 rounded-lg shadow transition"
                >
                  Download CSV
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Bottom Section: Leads Table */}
      <section className="max-w-7xl mx-auto px-6 mt-12">
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-6 backdrop-blur-xl shadow-xl">
          {/* Header Actions */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
                <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                </svg>
                Leads Database
              </h2>
              <p className="text-xs text-zinc-500 mt-1">
                Showing {filteredLeads.length} leads of {leads.length} total.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Search Bar */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="Filter leads..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="bg-zinc-950 border border-zinc-800 rounded-xl pl-9 pr-4 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 w-60"
                />
                <svg className="w-4 h-4 text-zinc-600 absolute left-3 top-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>

              {/* Action Buttons */}
              <button
                onClick={handleDownloadCSV}
                disabled={leads.length === 0}
                className="bg-zinc-850 hover:bg-zinc-800 border border-zinc-800 text-zinc-200 font-medium text-sm px-4 py-2 rounded-xl transition flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Export CSV
              </button>

              <button
                onClick={handleClearDatabase}
                disabled={leads.length === 0 || status.status === "running"}
                className="bg-rose-950/20 hover:bg-rose-950/40 border border-rose-900/30 text-rose-400 font-medium text-sm px-4 py-2 rounded-xl transition flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Clear Database
              </button>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto border border-zinc-800/80 rounded-xl bg-zinc-950/30">
            {isLoadingLeads ? (
              <div className="text-center py-20 text-zinc-500">
                <svg className="animate-spin h-8 w-8 mx-auto text-zinc-700 mb-2" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Loading leads database...
              </div>
            ) : filteredLeads.length === 0 ? (
              <div className="text-center py-20 text-zinc-500">
                <svg className="w-12 h-12 text-zinc-800 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
                </svg>
                {leads.length === 0 ? "No leads scraped yet." : "No leads match your filter."}
              </div>
            ) : (
              <table className="min-w-full divide-y divide-zinc-800/80">
                <thead>
                  <tr className="bg-zinc-900/30 text-zinc-400 text-[11px] font-bold uppercase tracking-wider text-left">
                    <th className="px-6 py-4">Name</th>
                    <th className="px-6 py-4">Phone</th>
                    <th className="px-6 py-4">Website</th>
                    <th className="px-6 py-4">SEO</th>
                    <th className="px-6 py-4">Rating</th>
                    <th className="px-6 py-4">Address</th>
                    <th className="px-6 py-4">Email</th>
                    <th className="px-6 py-4">Socials</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50 text-sm">
                  {filteredLeads.map((lead, idx) => (
                    <tr key={idx} className="hover:bg-zinc-900/20 transition-colors">
                      <td className="px-6 py-4 font-semibold text-zinc-200">{lead.name}</td>
                      <td className="px-6 py-4 font-mono text-zinc-300">
                        {lead.phone ? (
                          <div className="flex items-center gap-2">
                            <span>{lead.phone}</span>
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(lead.phone);
                              }}
                              title="Copy to clipboard"
                              className="text-zinc-600 hover:text-zinc-400 transition"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                              </svg>
                            </button>
                          </div>
                        ) : (
                          <span className="text-zinc-650 italic text-xs">None</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {lead.website ? (
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded font-medium truncate max-w-[150px]" title={lead.website}>
                                {lead.website.replace(/^https?:\/\/(www\.)?/, "")}
                              </span>
                              <a
                                href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-zinc-600 hover:text-indigo-400 transition"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                              </a>
                            </div>
                            {lead.screenshot && (
                              <a href={`${API_BASE}${lead.screenshot}`} target="_blank" rel="noopener noreferrer" className="block w-[100px] h-[56px] rounded border border-zinc-800 overflow-hidden hover:border-indigo-500 transition relative group bg-zinc-900">
                                <img src={`${API_BASE}${lead.screenshot}`} alt="Website Preview" className="w-full h-full object-cover object-top opacity-80 group-hover:opacity-100 transition" />
                                <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
                                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" /></svg>
                                </div>
                              </a>
                            )}
                          </div>
                        ) : (
                          <span className="px-2 py-0.5 bg-zinc-800 text-zinc-500 text-[11px] rounded font-medium">
                            No Website
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {lead.website ? (
                          <div className="flex flex-col gap-1">
                            <span className={`px-2 py-0.5 rounded text-[11px] font-bold w-max ${
                              (lead.seo_score ?? 0) >= 90 ? 'bg-emerald-500/20 text-emerald-400' :
                              (lead.seo_score ?? 0) >= 70 ? 'bg-amber-500/20 text-amber-400' :
                              'bg-rose-500/20 text-rose-400'
                            }`}>
                              {lead.seo_score ?? 0} / 100
                            </span>
                            {(lead.seo_issues && lead.seo_issues !== "Perfect SEO Basics") && (
                              <span className="text-[10px] text-zinc-500 leading-tight truncate max-w-[120px]" title={lead.seo_issues}>
                                {lead.seo_issues.split(",")[0]}...
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-zinc-650 italic text-xs">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {lead.rating > 0 ? (
                          <div className="flex items-center gap-1">
                            <span className="font-semibold text-zinc-200">{lead.rating}</span>
                            <span className="text-amber-500">★</span>
                            <span className="text-zinc-500 text-xs font-medium">({lead.reviews})</span>
                          </div>
                        ) : (
                          <span className="text-zinc-600 text-xs">No reviews</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-zinc-400 truncate max-w-xs" title={lead.address}>
                        {lead.address || <span className="text-zinc-650 italic text-xs">N/A</span>}
                      </td>
                      <td className="px-6 py-4 font-mono text-zinc-300">
                        {lead.email ? (
                          <div className="flex items-center gap-2">
                            <span className="truncate max-w-[120px] text-xs" title={lead.email}>{lead.email}</span>
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(lead.email || "");
                              }}
                              title="Copy email"
                              className="text-zinc-650 hover:text-zinc-450 transition"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                              </svg>
                            </button>
                          </div>
                        ) : (
                          <span className="text-zinc-650 italic text-xs">None</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          {lead.instagram ? (
                            <a
                              href={lead.instagram}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="Instagram"
                              className="text-zinc-500 hover:text-pink-400 transition"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                                <path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z" />
                                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" stroke="currentColor" strokeWidth="2" />
                              </svg>
                            </a>
                          ) : null}
                          {lead.facebook ? (
                            <a
                              href={lead.facebook}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="Facebook"
                              className="text-zinc-500 hover:text-blue-500 transition"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                <path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z" />
                              </svg>
                            </a>
                          ) : null}
                          {!lead.instagram && !lead.facebook && (
                            <span className="text-zinc-650 italic text-xs">None</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
