import { ChevronDown, LogOut } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";

function initialsOf(first: string, last: string, fallback: string): string {
  const letters = `${first.charAt(0)}${last.charAt(0)}`.trim();
  return (letters || fallback.slice(0, 2)).toUpperCase();
}

export function UserMenu() {
  const { me, logout } = useAuth();
  if (!me) return null;

  const fullName = `${me.first_name} ${me.last_name}`.trim() || me.username;
  const initials = initialsOf(me.first_name, me.last_name, me.username);
  const shortRole = fr.rolesShort[me.role];
  const longRole = fr.roles[me.role];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`${fr.shell.userMenu} : ${fullName}, ${longRole}`}
        className="flex h-10 items-center gap-2 rounded-md px-1 text-sm outline-offset-2 transition-colors hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-ring data-[state=open]:bg-surface-subtle lg:px-1.5"
      >
        <Initials initials={initials} />
        <span className="hidden font-medium lg:inline">{fullName}</span>
        <Badge
          variant="outline"
          className="hidden h-5 rounded-sm bg-background px-1.5 text-xs font-normal text-foreground lg:inline-flex"
        >
          {shortRole}
        </Badge>
        <ChevronDown className="hidden size-4 text-text-muted lg:block" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={4}
        className="w-[296px] rounded-lg bg-surface p-1 shadow-floating"
      >
        <div className="flex items-center gap-3 px-3 py-3">
          <Initials initials={initials} large />
          <div className="min-w-0">
            <p className="truncate font-semibold">{fullName}</p>
            <p className="truncate text-xs text-text-muted">{me.email}</p>
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 px-3 pb-3 text-xs text-text-muted">
          <span>{fr.shell.role}</span>
          <Badge
            variant="outline"
            className="h-5 rounded-sm bg-background px-1.5 text-xs font-normal text-foreground"
          >
            {longRole}
          </Badge>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="h-9 gap-3 px-3"
          onSelect={() => {
            void logout();
          }}
        >
          <LogOut aria-hidden />
          {fr.auth.logout}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function Initials({ initials, large = false }: { initials: string; large?: boolean }) {
  return (
    <Avatar size={large ? "lg" : "default"} aria-hidden>
      <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary ring-1 ring-primary/20 ring-inset">
        {initials}
      </AvatarFallback>
    </Avatar>
  );
}
