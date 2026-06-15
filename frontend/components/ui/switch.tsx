import * as React from "react";
import { cn } from "@/lib/utils";

export interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, ...props }, ref) => {
    return (
      <label className={cn("relative inline-flex cursor-pointer items-center", className)}>
        <input
          ref={ref}
          type="checkbox"
          className="peer sr-only"
          {...props}
        />
        <div className="h-5 w-9 rounded-full bg-noir-700 transition-colors peer-checked:bg-ls-500 after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-noir-100 after:transition-transform peer-checked:after:translate-x-4" />
      </label>
    );
  }
);
Switch.displayName = "Switch";

export { Switch };
