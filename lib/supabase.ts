import { createClient, SupabaseClient } from '@supabase/supabase-js'

// Single Supabase client for the browser (guards against multiple GoTrue clients, even across HMR)
const globalForSupabase = globalThis as typeof globalThis & { __supabaseBrowserClient?: SupabaseClient }
export const createBrowserClient = (): SupabaseClient | null => {
  if (globalForSupabase.__supabaseBrowserClient) return globalForSupabase.__supabaseBrowserClient
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/c06d0fd1-c297-47eb-9e68-2482808d33d7',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'780603'},body:JSON.stringify({sessionId:'780603',location:'supabase.ts:createBrowserClient:newInstance',message:'Creating new Supabase client',data:{hadExisting:!!globalForSupabase.__supabaseBrowserClient},hypothesisId:'H4',timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  globalForSupabase.__supabaseBrowserClient = createClient(url, key)
  return globalForSupabase.__supabaseBrowserClient
}

// For server components
export const createServerClient = (): SupabaseClient | null => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  
  if (!supabaseUrl || !supabaseAnonKey) {
    return null
  }
  return createClient(supabaseUrl, supabaseAnonKey)
}

// Get current session (uses shared client)
export const getSession = async () => {
  const client = createBrowserClient()
  if (!client) return null
  try {
    const { data: { session } } = await client.auth.getSession()
    return session
  } catch {
    return null
  }
}

// Get current user (uses shared client)
export const getUser = async () => {
  const client = createBrowserClient()
  if (!client) return null
  try {
    const { data: { user } } = await client.auth.getUser()
    return user
  } catch {
    return null
  }
}

// Legacy export for backward compatibility
export const createClientComponentClient = createBrowserClient

// Shared instance (same as createBrowserClient() after first call)
export const supabase = createBrowserClient()

// Backend API base URL (local-first mode)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Check if we're in local-first mode (no Supabase)
export const isLocalMode =
  process.env.NEXT_PUBLIC_FORCE_LOCAL_MODE === 'true' ||
  !supabase;

// Types for our database tables
export interface Document {
  id: string;
  user_id: string | null;
  file_name: string;
  file_type: 'pdf' | 'csv' | 'xlsx';
  file_url: string | null;
  format_detected: string | null;
  upload_date: string;
  status: 'uploaded' | 'processing' | 'partial' | 'completed' | 'failed';
  rows_count: number;
  rows_parsed?: number | null;
  rows_expected?: number | null;
  anomalies_count?: number;
  error_code?: string | null;
  error_message: string | null;
  next_action?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractedRow {
  id: string;
  document_id: string;
  row_index: number;
  raw_json: Record<string, any>;
  created_at: string;
}

// Helper function to upload file to Supabase Storage or backend
export async function uploadFile(file: File, userId: string) {
  if (isLocalMode || !supabase) {
    // Local mode: upload to backend and process asynchronously
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', userId);

    const response = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error('File upload failed');
    }

    const result = await response.json();
    return {
      path: file.name,
      url: `local://${file.name}`,
      document_id: result.document_id
    };
  }

  // Supabase mode
  const fileExt = file.name.split('.').pop();
  const fileName = `${userId}/${Date.now()}_${file.name}`;
  const filePath = `${fileName}`;

  const { data, error } = await supabase.storage
    .from('uploads')
    .upload(filePath, file, {
      cacheControl: '3600',
      upsert: false
    });

  if (error) {
    throw error;
  }

  // Get public URL
  const { data: urlData } = supabase.storage
    .from('uploads')
    .getPublicUrl(filePath);

  return {
    path: data.path,
    url: urlData.publicUrl
  };
}

// Helper function to create document record
export async function createDocument(
  userId: string,
  fileName: string,
  fileType: 'pdf' | 'csv' | 'xlsx',
  fileUrl: string
): Promise<Document> {
  if (isLocalMode || !supabase) {
    // Local mode: use backend API
    // Documents are created automatically during upload
    // Return a mock document for now
    return {
      id: Date.now().toString(),
      user_id: userId,
      file_name: fileName,
      file_type: fileType,
      file_url: fileUrl,
      format_detected: null,
      upload_date: new Date().toISOString(),
      status: 'uploaded',
      rows_count: 0,
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
  }

  // Supabase mode
  const { data, error } = await supabase
    .from('documents')
    .insert({
      user_id: userId,
      file_name: fileName,
      file_type: fileType,
      file_url: fileUrl,
      status: 'uploaded'
    })
    .select()
    .single();

  if (error) {
    throw error;
  }

  return data;
}

// Helper function to update document status
export async function updateDocumentStatus(
  documentId: string,
  status: Document['status'],
  rowsCount?: number,
  errorMessage?: string
) {
  if (isLocalMode || !supabase) {
    // Local mode: document status is managed by backend
    // Just return success
    return {
      id: documentId,
      status,
      rows_count: rowsCount || 0,
      error_message: errorMessage || null
    } as Document;
  }

  // Supabase mode
  const updateData: Partial<Document> = { status };
  if (rowsCount !== undefined) updateData.rows_count = rowsCount;
  if (errorMessage !== undefined) updateData.error_message = errorMessage;

  const { data, error } = await supabase
    .from('documents')
    .update(updateData)
    .eq('id', documentId)
    .select()
    .single();

  if (error) {
    throw error;
  }

  return data;
}

// Helper function to get documents for a user
export async function getDocuments(userId: string): Promise<Document[]> {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/c06d0fd1-c297-47eb-9e68-2482808d33d7',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'780603'},body:JSON.stringify({sessionId:'780603',location:'supabase.ts:getDocuments:entry',message:'getDocuments called',data:{userId,isLocalMode,hasSupabase:!!supabase},hypothesisId:'H2,H3',timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  if (isLocalMode || !supabase) {
    // Local mode: use backend API
    const url = userId ? `${API_BASE}/documents?session_id=${encodeURIComponent(userId)}` : `${API_BASE}/documents`;
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeout);

      if (!response.ok) {
        return [];
      }

      const data = await response.json().catch(() => ([]));
      return data || [];
    } catch {
      return [];
    }
  }

  // Supabase mode
  const { data, error } = await supabase
    .from('documents')
    .select('*')
    .eq('user_id', userId)
    .order('upload_date', { ascending: false });

  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/c06d0fd1-c297-47eb-9e68-2482808d33d7',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'780603'},body:JSON.stringify({sessionId:'780603',location:'supabase.ts:getDocuments:supabaseResult',message:'Supabase query result',data:{rowCount:data?.length??0,error:error?.message,userId},hypothesisId:'H2,H3',timestamp:Date.now()})}).catch(()=>{});
  // #endregion

  if (error) {
    throw error;
  }

  return data || [];
}

// Helper function to get extracted rows for a document
export async function getExtractedRows(documentId: string): Promise<ExtractedRow[]> {
  if (isLocalMode || !supabase) {
    // Local mode: use backend API
    const response = await fetch(`${API_BASE}/document/${documentId}/rows`);
    if (!response.ok) {
      throw new Error('Failed to fetch rows');
    }
    const data = await response.json();
    // Transform backend response format to expected format
    return (data.rows || []).map((row: any) => ({
      id: `${row.row_index}`,
      document_id: documentId,
      row_index: row.row_index,
      raw_json: row.raw_json,
      created_at: new Date().toISOString()
    }));
  }

  // Supabase mode
  const { data, error } = await supabase
    .from('extracted_rows')
    .select('*')
    .eq('document_id', documentId)
    .order('row_index', { ascending: true });

  if (error) {
    throw error;
  }

  return data || [];
}

// Helper function to delete a document and its extracted rows
export async function deleteDocument(documentId: string) {
  if (isLocalMode || !supabase) {
    // Local mode: use backend API
    try {
      const response = await fetch(`${API_BASE}/document/${documentId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}: Failed to delete document`);
      }

      const result = await response.json();
      return result;
    } catch (err: any) {
      // If it's already an Error, re-throw it
      if (err instanceof Error) {
        throw err;
      }
      throw new Error(`Failed to delete document: ${err.message || 'Unknown error'}`);
    }
  }

  // Supabase mode
  const { error } = await supabase
    .from('documents')
    .delete()
    .eq('id', documentId);

  if (error) {
    throw new Error(error.message || 'Failed to delete document');
  }
}


