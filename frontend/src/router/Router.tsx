import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

interface RouterContextType {
  pathname: string;
  navigate: (to: string) => void;
  params: Record<string, string>;
  setParams: (params: Record<string, string>) => void;
}

const RouterContext = createContext<RouterContextType | undefined>(undefined);

// Standalone global navigate helper
let globalNavigate: ((to: string) => void) | null = null;
export const navigate = (to: string) => {
  if (globalNavigate) {
    globalNavigate(to);
  } else {
    window.history.pushState({}, '', to);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
};

// Helper to get current path from either pathname or hash (for flexibility)
function getInitialPath(): string {
  if (window.location.hash && window.location.hash.startsWith('#/')) {
    return window.location.hash.slice(1);
  }
  return window.location.pathname || '/';
}

export const RouterProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [pathname, setPathname] = useState<string>(getInitialPath);
  const [params, setParams] = useState<Record<string, string>>({});

  useEffect(() => {
    const handlePopState = () => {
      setPathname(getInitialPath());
    };

    window.addEventListener('popstate', handlePopState);
    window.addEventListener('hashchange', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('hashchange', handlePopState);
    };
  }, []);

  const handleNavigate = useCallback((to: string) => {
    if (to === pathname) return;
    window.history.pushState({}, '', to);
    setPathname(to);
    window.scrollTo(0, 0);
  }, [pathname]);

  useEffect(() => {
    globalNavigate = handleNavigate;
    return () => {
      globalNavigate = null;
    };
  }, [handleNavigate]);

  return (
    <RouterContext.Provider value={{ pathname, navigate: handleNavigate, params, setParams }}>
      {children}
    </RouterContext.Provider>
  );
};

export const useRouter = (): RouterContextType => {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error('useRouter must be used within a RouterProvider');
  }
  return context;
};

export const useNavigate = () => {
  const { navigate } = useRouter();
  return navigate;
};

export const useLocation = () => {
  const { pathname } = useRouter();
  return { pathname };
};

export const useParams = (): Record<string, string> => {
  const { params } = useRouter();
  return params;
};

export const useRouteParams = useParams;

interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string;
  children: React.ReactNode;
}

export const Link: React.FC<LinkProps> = ({ to, children, className, onClick, ...rest }) => {
  const { navigate } = useRouter();

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onClick) onClick(e);
    if (!e.defaultPrevented && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      navigate(to);
    }
  };

  return (
    <a href={to} onClick={handleClick} className={className} {...rest}>
      {children}
    </a>
  );
};

interface RouteProps {
  path: string;
  element: React.ReactElement;
}

export interface RouteMatchResult {
  matched: boolean;
  params: Record<string, string>;
}

export function matchPath(pattern: string, pathname: string): RouteMatchResult {
  const patternParts = pattern.split('/').filter(Boolean);
  const pathParts = pathname.split('?')[0].split('/').filter(Boolean);

  if (patternParts.length !== pathParts.length) {
    return { matched: false, params: {} };
  }

  const params: Record<string, string> = {};

  for (let i = 0; i < patternParts.length; i++) {
    const patternPart = patternParts[i];
    const pathPart = pathParts[i];

    if (patternPart.startsWith(':')) {
      const paramName = patternPart.slice(1);
      params[paramName] = decodeURIComponent(pathPart);
    } else if (patternPart !== pathPart) {
      return { matched: false, params: {} };
    }
  }

  return { matched: true, params };
}

interface RoutesProps {
  children: React.ReactElement<RouteProps> | Array<React.ReactElement<RouteProps> | null>;
}

export const Routes: React.FC<RoutesProps> = ({ children }) => {
  const { pathname, setParams } = useRouter();

  let matchedElement: React.ReactElement | null = null;
  let matchedParams: Record<string, string> = {};

  const routeChildren = React.Children.toArray(children) as React.ReactElement<RouteProps>[];

  for (const child of routeChildren) {
    if (!React.isValidElement(child)) continue;
    const { path, element } = child.props;

    if (path === '*') {
      if (!matchedElement) {
        matchedElement = element;
      }
      continue;
    }

    const { matched, params } = matchPath(path, pathname);
    if (matched) {
      matchedElement = element;
      matchedParams = params;
      break;
    }
  }

  useEffect(() => {
    setParams(matchedParams);
  }, [JSON.stringify(matchedParams)]);

  if (matchedElement) {
    return React.cloneElement(matchedElement, { ...matchedParams });
  }

  return null;
};

export const Route: React.FC<RouteProps> = () => null;
