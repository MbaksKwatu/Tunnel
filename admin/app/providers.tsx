'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

export type Env = 'prod' | 'staging'

interface EnvContextValue {
  env: Env
  setEnv: (env: Env) => void
}

const EnvContext = createContext<EnvContextValue>({ env: 'prod', setEnv: () => {} })

const STORAGE_KEY = 'parity-admin-env'

export function Providers({ children }: { children: ReactNode }) {
  const [env, setEnvState] = useState<Env>('prod')

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'prod' || stored === 'staging') setEnvState(stored)
  }, [])

  function setEnv(next: Env) {
    setEnvState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }

  return (
    <EnvContext.Provider value={{ env, setEnv }}>
      {children}
    </EnvContext.Provider>
  )
}

export function useEnv() {
  return useContext(EnvContext)
}
