import { ChevronDown, CircleHelp, KeyRound, LogOut, UserRound } from "lucide-react";
import { Link } from "react-router-dom";
import { useTutoriel } from "@/features/tutoriel/context";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AUTH_PATHS } from "@/auth/paths";
import { useAuth } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";
import { initialsOf } from "./initials";

const ROLE_BADGE = "h-5 rounded-sm bg-background px-1.5 text-xs font-normal text-foreground";

export function UserMenu() {
  const { me, logout } = useAuth();
  const { relancer } = useTutoriel();
  if (!me) return null;

  const fullName = `${me.first_name ?? ""} ${me.last_name ?? ""}`.trim() || me.username;
  const initials = initialsOf(me.first_name, me.last_name, me.username);

  // Le nom accessible commence par le texte visible (WCAG 2.5.3) ; sous 1024 px le texte
  // visible se réduit à l'avatar, nom et rôle restent lus.
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        data-tour="menu-utilisateur"
        className="flex h-10 items-center gap-2 rounded-md px-1 text-sm transition-colors hover:bg-surface-subtle data-[state=open]:bg-surface-subtle lg:px-1.5"
      >
        <Initials initials={initials} />
        <span className="font-medium max-lg:sr-only">{fullName}</span>{" "}
        <Badge variant="outline" className={`${ROLE_BADGE} max-lg:sr-only`}>
          {fr.rolesShort[me.role]}
        </Badge>{" "}
        <span className="sr-only">{`— ${fr.shell.userMenu}`}</span>
        <ChevronDown className="size-4 text-text-muted max-lg:hidden" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={12}
        className="w-[296px] rounded-lg bg-surface p-1"
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
          <Badge variant="outline" className={ROLE_BADGE}>
            {fr.roles[me.role]}
          </Badge>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="h-9 gap-3 px-3">
          <Link to="/mon-compte">
            <UserRound aria-hidden />
            {fr.tutoriel.menuAccount}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild className="h-9 gap-3 px-3">
          <Link to={AUTH_PATHS.change} state={{ from: "/mon-compte" }}>
            <KeyRound aria-hidden />
            {fr.tutoriel.menuPassword}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem className="h-9 gap-3 px-3" onSelect={relancer}>
          <CircleHelp aria-hidden />
          {fr.tutoriel.menuTour}
        </DropdownMenuItem>
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
