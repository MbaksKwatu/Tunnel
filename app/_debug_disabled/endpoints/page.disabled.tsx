'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, AlertCircle, Loader2, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export default function EndpointDebugPage() {
    const [results, setResults] = useState<{
        endpoint: string;
        status: 'pending' | 'ok' | 'fail';
        latency?: number;
        error?: string;
    }[]>([]);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL;

    const endpoints = [
        { name: 'Health Check', path: '/health', method: 'GET' },
        { name: 'Documents List', path: '/documents', method: 'GET' },
    ];

    const testEndpoints = async () => {
        setResults(endpoints.map(e => ({
            endpoint: `${e.method} ${e.path}`,
            status: 'pending'
        })));

        for (const ep of endpoints) {
            const start = performance.now();
            try {
                const response = await fetch(`${API_BASE}${ep.path}`, {
                    method: ep.method,
                    // Add a timeout to prevent hanging
                    signal: AbortSignal.timeout(5000)
                });

                const end = performance.now();
                const latency = Math.round(end - start);

                if (response.ok) {
                    updateResult(`${ep.method} ${ep.path}`, 'ok', latency);
                } else {
                    updateResult(`${ep.method} ${ep.path}`, 'fail', latency, `HTTP ${response.status}`);
                }
            } catch (error: any) {
                const end = performance.now();
                const latency = Math.round(end - start);
                updateResult(`${ep.method} ${ep.path}`, 'fail', latency, error.message);
            }
        }
    };

    const updateResult = (endpoint: string, status: 'ok' | 'fail', latency: number, error?: string) => {
        setResults(prev => prev.map(r =>
            r.endpoint === endpoint ? { ...r, status, latency, error } : r
        ));
    };

    useEffect(() => {
        testEndpoints();
    }, []);

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-2xl mx-auto">
                <div className="mb-6 flex items-center gap-4">
                    <Link href="/connect-data" className="text-gray-500 hover:text-gray-900">
                        <ArrowLeft className="w-6 h-6" />
                    </Link>
                    <h1 className="text-2xl font-bold text-gray-900">Backend Endpoint Validator</h1>
                </div>

                <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                        <div className="text-sm text-gray-500 font-mono">
                            API_URL: <span className="font-bold text-gray-900">{API_BASE || '(undefined)'}</span>
                        </div>
                        <button
                            onClick={testEndpoints}
                            className="px-3 py-1 text-sm bg-white border border-gray-300 rounded hover:bg-gray-50"
                        >
                            Rerun Tests
                        </button>
                    </div>

                    <div className="divide-y divide-gray-100">
                        {results.map((result) => (
                            <div key={result.endpoint} className="p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    {result.status === 'pending' && <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />}
                                    {result.status === 'ok' && <CheckCircle className="w-5 h-5 text-green-500" />}
                                    {result.status === 'fail' && <XCircle className="w-5 h-5 text-red-500" />}

                                    <div>
                                        <div className="font-medium font-mono text-sm">{result.endpoint}</div>
                                        {result.error && (
                                            <div className="text-xs text-red-600 mt-1">{result.error}</div>
                                        )}
                                    </div>
                                </div>

                                <div className="text-sm font-mono text-gray-500">
                                    {result.latency !== undefined ? `${result.latency}ms` : '-'}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {results.some(r => r.status === 'fail') && (
                    <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
                        <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />
                        <div className="text-sm text-red-800">
                            <p className="font-semibold mb-1">Connectivity Issues Detected</p>
                            <p>Ensure that:</p>
                            <ul className="list-disc pl-4 mt-1 space-y-1">
                                <li>The backend is running and reachable.</li>
                                <li>The <code>NEXT_PUBLIC_API_URL</code> environment variable is set correctly in Vercel.</li>
                                <li>CORS is enabled on the backend for this domain.</li>
                            </ul>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
