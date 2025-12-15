'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import { 
  Building2, 
  LayoutDashboard, 
  FileText, 
  Calendar, 
  ChevronRight, 
  Loader2,
  Plus,
  RefreshCw
} from 'lucide-react';
import Sidebar from '@/components/Layout/Sidebar';

interface Investee {
  investee_name: string;
  last_uploaded: string;
}

interface Dashboard {
  id: string;
  investee_name: string;
  dashboard_name: string;
  created_at: string;
}

interface Report {
  id: string;
  investee_name: string;
  report_name: string;
  report_type: string;
  storage_path: string;
  created_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [investees, setInvestees] = useState<Investee[]>([]);
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'investees' | 'dashboards' | 'reports'>('investees');

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    setIsLoading(true);
    try {
      const [investeesRes, dashboardsRes, reportsRes] = await Promise.all([
        axios.get(`${apiUrl}/investees`),
        axios.get(`${apiUrl}/dashboards`),
        axios.get(`${apiUrl}/reports`)
      ]);
      
      setInvestees(investeesRes.data);
      setDashboards(dashboardsRes.data);
      setReports(reportsRes.data);
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
      });
    } catch {
      return dateString;
    }
  };

  const handleOpenInvestee = (investeeName: string) => {
    router.push(`/actions/evaluate?investee=${encodeURIComponent(investeeName)}`);
  };

  const handleOpenDashboard = (dashboardId: string) => {
    router.push(`/actions/evaluate?dashboard=${dashboardId}`);
  };

  const tabs = [
    { id: 'investees', label: 'Investees', icon: Building2, count: investees.length },
    { id: 'dashboards', label: 'Saved Dashboards', icon: LayoutDashboard, count: dashboards.length },
    { id: 'reports', label: 'Reports', icon: FileText, count: reports.length },
  ];

  return (
    <div className="flex min-h-screen bg-base-950">
      <Sidebar />
      
      <main className="flex-1 p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Dashboard</h1>
            <p className="text-slate-400 mt-1">Manage your investees, dashboards, and reports</p>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={fetchAllData}
              className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-5 h-5 text-slate-400 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => router.push('/upload')}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 
                         text-white rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              Upload Document
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-slate-800 pb-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors
                         ${activeTab === tab.id 
                           ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50' 
                           : 'bg-slate-800/50 text-slate-400 hover:bg-slate-800 border border-transparent'
                         }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
              <span className={`px-2 py-0.5 text-xs rounded-full 
                              ${activeTab === tab.id ? 'bg-blue-500/30' : 'bg-slate-700'}`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
          </div>
        ) : (
          <div className="space-y-3">
            {/* Investees Tab */}
            {activeTab === 'investees' && (
              investees.length === 0 ? (
                <EmptyState 
                  icon={Building2}
                  title="No investees yet"
                  description="Upload a document to create your first investee"
                  action={() => router.push('/upload')}
                  actionLabel="Upload Document"
                />
              ) : (
                investees.map((investee) => (
                  <div
                    key={investee.investee_name}
                    onClick={() => handleOpenInvestee(investee.investee_name)}
                    className="flex items-center justify-between p-4 bg-dark-card border border-slate-800 
                               rounded-lg hover:border-slate-700 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-slate-800 rounded-lg group-hover:bg-slate-700 transition-colors">
                        <Building2 className="w-5 h-5 text-blue-400" />
                      </div>
                      <div>
                        <h3 className="font-medium text-white">{investee.investee_name}</h3>
                        <div className="flex items-center gap-1 text-sm text-slate-500 mt-0.5">
                          <Calendar className="w-3.5 h-3.5" />
                          <span>Last updated: {formatDate(investee.last_uploaded)}</span>
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                  </div>
                ))
              )
            )}

            {/* Dashboards Tab */}
            {activeTab === 'dashboards' && (
              dashboards.length === 0 ? (
                <EmptyState 
                  icon={LayoutDashboard}
                  title="No saved dashboards"
                  description="Create and save a dashboard from the Evaluate view"
                />
              ) : (
                dashboards.map((dashboard) => (
                  <div
                    key={dashboard.id}
                    onClick={() => handleOpenDashboard(dashboard.id)}
                    className="flex items-center justify-between p-4 bg-dark-card border border-slate-800 
                               rounded-lg hover:border-slate-700 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-slate-800 rounded-lg group-hover:bg-slate-700 transition-colors">
                        <LayoutDashboard className="w-5 h-5 text-green-400" />
                      </div>
                      <div>
                        <h3 className="font-medium text-white">{dashboard.dashboard_name}</h3>
                        <div className="flex items-center gap-2 text-sm text-slate-500 mt-0.5">
                          <span>{dashboard.investee_name}</span>
                          <span>•</span>
                          <span>{formatDate(dashboard.created_at)}</span>
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                  </div>
                ))
              )
            )}

            {/* Reports Tab */}
            {activeTab === 'reports' && (
              reports.length === 0 ? (
                <EmptyState 
                  icon={FileText}
                  title="No reports generated"
                  description="Generate an IC Report from the Evaluate view"
                />
              ) : (
                reports.map((report) => (
                  <div
                    key={report.id}
                    className="flex items-center justify-between p-4 bg-dark-card border border-slate-800 
                               rounded-lg hover:border-slate-700 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-slate-800 rounded-lg group-hover:bg-slate-700 transition-colors">
                        <FileText className="w-5 h-5 text-purple-400" />
                      </div>
                      <div>
                        <h3 className="font-medium text-white">{report.report_name}</h3>
                        <div className="flex items-center gap-2 text-sm text-slate-500 mt-0.5">
                          <span>{report.investee_name}</span>
                          <span>•</span>
                          <span className="capitalize">{report.report_type.replace('_', ' ')}</span>
                          <span>•</span>
                          <span>{formatDate(report.created_at)}</span>
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                  </div>
                ))
              )
            )}
          </div>
        )}
      </main>
    </div>
  );
}

// Empty State Component
function EmptyState({ 
  icon: Icon, 
  title, 
  description, 
  action, 
  actionLabel 
}: { 
  icon: any; 
  title: string; 
  description: string; 
  action?: () => void; 
  actionLabel?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="p-4 bg-slate-800/50 rounded-full mb-4">
        <Icon className="w-8 h-8 text-slate-500" />
      </div>
      <h3 className="text-lg font-medium text-slate-300">{title}</h3>
      <p className="text-sm text-slate-500 mt-1 max-w-sm">{description}</p>
      {action && actionLabel && (
        <button
          onClick={action}
          className="mt-4 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
