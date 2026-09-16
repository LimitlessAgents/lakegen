import React from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="flex min-h-full items-center justify-center bg-canvas p-8 text-center">
          <div>
            <h1 className="text-[16px] font-medium text-ink">LakeGen could not load</h1>
            <p className="mt-2 text-[14px] text-ink-muted">
              Reload the page to try again.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-5 rounded-md bg-ink px-3 py-2 text-[13px] font-medium text-white hover:bg-black"
            >
              Reload
            </button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
