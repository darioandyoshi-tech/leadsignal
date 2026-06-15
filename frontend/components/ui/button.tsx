import * as React from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg";
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", asChild = false, children, ...props }, ref) => {
    const variants = {
      default: "bg-ls-500 text-noir-950 hover:bg-ls-400",
      outline: "border border-noir-700 bg-transparent text-noir-100 hover:bg-noir-800",
      ghost: "bg-transparent text-noir-100 hover:bg-noir-800",
    };
    const sizes = {
      default: "h-9 px-4 py-2",
      sm: "h-8 px-3 text-sm",
      lg: "h-11 px-8",
    };
    const classes = cn(
      "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus:outline-none disabled:opacity-50",
      variants[variant],
      sizes[size],
      className
    );
    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children as React.ReactElement, {
        className: cn(classes, (children as React.ReactElement).props.className),
        ref,
        ...props,
      });
    }
    return (
      <button
        ref={ref}
        className={classes}
        {...props}
      >
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export { Button };
