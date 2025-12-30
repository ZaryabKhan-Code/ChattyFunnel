const API_URL = 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

export interface AttachmentUploadResponse {
  file_url: string
  file_name: string
  file_size: number
  mime_type: string
  storage_path: string
}

export async function uploadAttachment(
  file: File,
  userId: number,
  isVoiceNote = false
): Promise<AttachmentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(
    `${API_URL}/attachments/upload?user_id=${userId}&is_voice_note=${isVoiceNote}`,
    {
      method: 'POST',
      body: formData,
    }
  )

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to upload attachment')
  }

  return response.json()
}

export async function deleteAttachment(fileUrl: string, userId: number): Promise<void> {
  const response = await fetch(
    `${API_URL}/attachments/delete?file_url=${encodeURIComponent(fileUrl)}&user_id=${userId}`,
    {
      method: 'DELETE',
    }
  )

  if (!response.ok) throw new Error('Failed to delete attachment')
}
