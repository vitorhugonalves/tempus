import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";

type AlertVariant = "info" | "success" | "warning" | "error";

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
}

const config: Record<
  AlertVariant,
  { containerClass: string; iconClass: string; Icon: React.ElementType }
> = {
  info: {
    containerClass: "bg-blue-50 border-blue-200 text-blue-800",
    iconClass: "text-blue-500",
    Icon: InformationCircleIcon,
  },
  success: {
    containerClass: "bg-green-50 border-green-200 text-green-800",
    iconClass: "text-green-500",
    Icon: CheckCircleIcon,
  },
  warning: {
    containerClass: "bg-yellow-50 border-yellow-200 text-yellow-800",
    iconClass: "text-yellow-500",
    Icon: ExclamationCircleIcon,
  },
  error: {
    containerClass: "bg-red-50 border-red-200 text-red-800",
    iconClass: "text-red-500",
    Icon: XCircleIcon,
  },
};

export default function Alert({ variant = "info", title, children }: AlertProps) {
  const { containerClass, iconClass, Icon } = config[variant];

  return (
    <div className={["flex gap-3 rounded-lg border p-4", containerClass].join(" ")}>
      <Icon className={["h-5 w-5 flex-shrink-0 mt-0.5", iconClass].join(" ")} />
      <div className="text-sm">
        {title && <p className="font-medium mb-1">{title}</p>}
        <p>{children}</p>
      </div>
    </div>
  );
}
