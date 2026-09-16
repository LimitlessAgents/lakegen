export function canCopyText(): boolean {
  return (
    (typeof navigator !== 'undefined' && typeof navigator.clipboard?.writeText === 'function') ||
    (typeof document !== 'undefined' &&
      typeof document.queryCommandSupported === 'function' &&
      document.queryCommandSupported('copy'))
  );
}

export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.clipboard?.writeText === 'function') {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.append(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    textarea.remove();
    return copied;
  } catch {
    return false;
  }
}
