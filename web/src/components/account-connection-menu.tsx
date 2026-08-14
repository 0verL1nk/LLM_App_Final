import { Cloud, HardDrive, Settings, UserCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type AccountConnectionMenuProps = {
  onOpenSettings: () => void;
};

/** Shows the actual local connection and reserves cloud mode until authentication exists. */
export function AccountConnectionMenu({ onOpenSettings }: AccountConnectionMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          aria-label="打开账户与连接设置"
          className="w-full justify-start gap-3 px-2"
          variant="ghost"
        >
          <UserCircle2 className="size-5" />
          <span className="min-w-0 flex-1 text-left">
            <span className="block truncate text-sm font-medium">本地用户</span>
            <span className="block truncate text-xs text-muted-foreground">本地工作区</span>
          </span>
          <HardDrive className="size-4 text-emerald-600" aria-label="本地模式" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>账户与连接</DropdownMenuLabel>
        <DropdownMenuRadioGroup value="local">
          <DropdownMenuRadioItem value="local">
            <HardDrive className="mr-2 size-4" />
            <span className="flex-1">本地模式</span>
            <Badge variant="secondary">当前</Badge>
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem disabled value="cloud">
            <Cloud className="mr-2 size-4" />
            <span className="flex-1">云端模式</span>
            <Badge variant="outline">暂不可用</Badge>
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <p className="px-2 py-2 text-xs leading-5 text-muted-foreground">
          云端模式将在账号认证与服务兼容性检查完成后开放。
        </p>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onOpenSettings}>
          <Settings className="mr-2 size-4" />
          模型与本地设置
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
