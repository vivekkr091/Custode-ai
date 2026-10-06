import React, { useState } from 'react';
import { CheckIcon, CopyIcon } from './Icons';

export const CodeView: React.FC<{
  data?: any;
  code?: any;
  label?: string;
  language?: string;
  maxHeight?: string;
}> = ({ data, code, label, language, maxHeight = '300px' }) => {
  const [copied, setCopied] = useState(false);
  const target = data !== undefined ? data : code;
  const formatted = typeof target === 'string' ? target : JSON.stringify(target, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(formatted);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-viewer-container">
      <div className="code-viewer-header">
        <span className="code-viewer-label">{label || (language ? language.toUpperCase() : 'JSON PAYLOAD')}</span>
        <button className="code-copy-btn" onClick={handleCopy} title="Copy to clipboard">
          {copied ? (
            <>
              <CheckIcon size={13} />
              <span>Copied</span>
            </>
          ) : (
            <>
              <CopyIcon size={13} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="code-viewer-pre" style={{ maxHeight }}>
        <code>{formatted}</code>
      </pre>
    </div>
  );
};
