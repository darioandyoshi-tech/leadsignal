import * as React from "react";
import { cn } from "@/lib/utils";

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          "flex h-10 w-full appearance-none rounded-md border border-noir-700 bg-noir-900 px-3 py-2 text-sm text-noir-100 focus:outline-none focus:ring-2 focus:ring-ls-500 focus:ring-offset-noir-900",
          className
        )}
        {...props}
      />
    );
  }
);
Select.displayName = "Select";

export { Select };
