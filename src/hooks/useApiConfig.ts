import { useEffect, useState } from 'react'
import { FALLBACK_CONFIG, getApiConfig, getErrorMessage, type ApiConfig } from '../api/client'

type ConfigState = {
  config: ApiConfig
  loading: boolean
  error: string
}

export function useApiConfig(): ConfigState {
  const [state, setState] = useState<ConfigState>({
    config: FALLBACK_CONFIG,
    loading: true,
    error: '',
  })

  useEffect(() => {
    let active = true

    getApiConfig()
      .then((config) => {
        if (active) {
          setState({ config, loading: false, error: '' })
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setState({
            config: FALLBACK_CONFIG,
            loading: false,
            error: getErrorMessage(error),
          })
        }
      })

    return () => {
      active = false
    }
  }, [])

  return state
}
