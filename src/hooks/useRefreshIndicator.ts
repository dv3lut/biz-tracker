import { useEffect, useRef, useState } from "react";

type Options = {
  delay?: number;
  minVisible?: number;
};

const DEFAULT_DELAY = 450;
const DEFAULT_MIN_VISIBLE = 350;

export const useRefreshIndicator = (isActive: boolean, options?: Options): boolean => {
  const { delay = DEFAULT_DELAY, minVisible = DEFAULT_MIN_VISIBLE } = options ?? {};
  const [visible, setVisible] = useState(false);
  const showTimer = useRef<number | null>(null);
  const hideTimer = useRef<number | null>(null);
  const visibleSince = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (showTimer.current !== null) {
        window.clearTimeout(showTimer.current);
        showTimer.current = null;
      }
      if (hideTimer.current !== null) {
        window.clearTimeout(hideTimer.current);
        hideTimer.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (isActive) {
      if (hideTimer.current !== null) {
        window.clearTimeout(hideTimer.current);
        hideTimer.current = null;
      }
      if (visible || showTimer.current !== null) {
        return;
      }
      showTimer.current = window.setTimeout(() => {
        showTimer.current = null;
        visibleSince.current = Date.now();
        setVisible(true);
      }, delay);
      return;
    }

    if (showTimer.current !== null) {
      window.clearTimeout(showTimer.current);
      showTimer.current = null;
    }

    if (!visible) {
      return;
    }

    const elapsed = visibleSince.current ? Date.now() - visibleSince.current : 0;

    if (elapsed >= minVisible) {
      visibleSince.current = null;
      setVisible(false);
      return;
    }

    if (hideTimer.current !== null) {
      window.clearTimeout(hideTimer.current);
    }
    hideTimer.current = window.setTimeout(() => {
      hideTimer.current = null;
      visibleSince.current = null;
      setVisible(false);
    }, minVisible - elapsed);
  }, [delay, isActive, minVisible, visible]);

  return visible;
};
