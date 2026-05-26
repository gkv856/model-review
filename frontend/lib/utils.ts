import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export const cn = (...inputs: ClassValue[]): string => {
  return twMerge(clsx(inputs));
};

// Input: bytes (number)
// Output: human-readable size string
export const formatFileSize = (bytes: number): string => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// Input: ISO date string
// Output: formatted local datetime string
export const formatDate = (iso: string): string => {
  return new Date(iso).toLocaleString();
};
