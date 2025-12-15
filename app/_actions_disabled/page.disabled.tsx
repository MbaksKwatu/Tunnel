'use client';

import { motion } from 'framer-motion';
import AppLayout from '@/components/Layout/AppLayout';
import FeatureCard from '@/components/FeatureCard';
import { Zap, MessageSquare, Mail, ArrowRight } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function ActionsPage() {
  const router = useRouter();

  return (
    <AppLayout>
      <div className="p-8 max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center gap-4 mb-8">
             <div className="p-3 bg-green-500/10 rounded-xl">
                <Zap className="w-8 h-8 text-green-400" />
             </div>
             <div>
                <h1 className="text-3xl font-bold text-white">Actions</h1>
                <p className="text-gray-400">Take decisive steps with AI assistance.</p>
             </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* Evaluate with Assistant */}
            <FeatureCard
              icon={MessageSquare}
              title="Evaluate with Assistant"
              description="Interactive AI session to drill down into financials, visualize trends, and answer due diligence questions."
            >
              <div className="mt-4">
                <button
                    onClick={() => router.push('/actions/evaluate')}
                    className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-cyan-500 hover:bg-cyan-600 text-black font-semibold rounded-lg transition-all"
                >
                    Open Assistant <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </FeatureCard>

            {/* Request Review */}
            <FeatureCard
              icon={Mail}
              title="Request Review"
              description="Draft professional emails to portfolio companies requesting missing documents or clarifications."
            >
               <div className="mt-4">
                <button
                    onClick={() => router.push('/actions/request-review')}
                    className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all"
                >
                    Compose Request <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </FeatureCard>

          </div>
        </motion.div>
      </div>
    </AppLayout>
  );
}
