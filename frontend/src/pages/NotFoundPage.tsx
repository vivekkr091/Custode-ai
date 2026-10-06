import React from 'react';
import { Button } from '../components/common/Button';
import { navigate } from '../router/Router';
import { ShieldAlertIcon, ArrowLeftIcon } from '../components/common/Icons';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center p-6 space-y-4">
      <div className="w-16 h-16 rounded-full bg-danger/10 border border-danger/30 flex items-center justify-center text-danger">
        <ShieldAlertIcon className="w-8 h-8" />
      </div>
      <div>
        <h1 className="text-3xl font-bold font-mono text-text-primary">404 - Not Found</h1>
        <p className="text-xs text-text-secondary font-mono mt-1">
          The requested control plane resource or route does not exist.
        </p>
      </div>
      <Button
        variant="primary"
        onClick={() => navigate('/')}
        leftIcon={<ArrowLeftIcon className="w-4 h-4" />}
      >
        Return to Security Dashboard
      </Button>
    </div>
  );
};
