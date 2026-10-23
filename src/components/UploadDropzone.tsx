import { FileImage, FileVideo2, UploadCloud } from 'lucide-react'
import { DragEvent, KeyboardEvent, useId, useRef, useState } from 'react'
import { formatFileSize } from '../api/client'

type UploadDropzoneProps = {
  kind: 'image' | 'video'
  file: File | null
  previewUrl: string
  accept: string
  disabled?: boolean
  helper: string
  onFileSelect: (file: File) => void
}

function UploadDropzone({
  kind,
  file,
  previewUrl,
  accept,
  disabled = false,
  helper,
  onFileSelect,
}: UploadDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const helperId = useId()
  const FileIcon = kind === 'image' ? FileImage : FileVideo2

  const chooseFile = () => {
    if (!disabled) {
      inputRef.current?.click()
    }
  }

  const handleKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      chooseFile()
    }
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    if (!disabled && event.dataTransfer.files[0]) {
      onFileSelect(event.dataTransfer.files[0])
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        aria-label={`Chọn ${kind === 'image' ? 'ảnh' : 'video'} để phân tích`}
        accept={accept}
        disabled={disabled}
        tabIndex={-1}
        onChange={(event) => {
          const nextFile = event.target.files?.[0]
          if (nextFile) {
            onFileSelect(nextFile)
          }
          event.target.value = ''
        }}
      />
      <div
        className="tool-dropzone"
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-describedby={helperId}
        data-dragging={dragging}
        onClick={chooseFile}
        onKeyDown={handleKeyboard}
        onDragEnter={(event) => {
          event.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setDragging(false)
          }
        }}
        onDrop={handleDrop}
      >
        <span id={helperId} className="sr-only">{helper}</span>
        {previewUrl ? (
          <>
            {kind === 'image' ? (
              <img className="tool-dropzone-preview" src={previewUrl} alt="Bản xem trước tệp đã chọn" />
            ) : (
              <video
                className="tool-dropzone-preview"
                src={previewUrl}
                muted
                playsInline
                preload="metadata"
                aria-label="Bản xem trước video đã chọn"
              />
            )}
            <span className="tool-dropzone-shade">
              <span className="tool-file-name">{file?.name}</span>
              <span className="tool-file-detail">
                {file ? formatFileSize(file.size) : ''} · Nhấn để chọn tệp khác
              </span>
            </span>
          </>
        ) : (
          <span>
            <span className="tool-dropzone-icon">
              <UploadCloud size={22} strokeWidth={1.7} aria-hidden="true" />
            </span>
            <strong className="tool-dropzone-title">Kéo thả hoặc chọn {kind === 'image' ? 'ảnh' : 'video'}</strong>
            <span className="tool-dropzone-copy">
              {helper}
            </span>
            <span className="tool-dropzone-file-type">
              <FileIcon size={13} aria-hidden="true" /> Chọn từ thiết bị
            </span>
          </span>
        )}
      </div>
    </>
  )
}

export default UploadDropzone
