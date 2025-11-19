import { Link, useLocation } from "react-router-dom";
import { UploadCloud, Package, Webhook } from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Import", href: "/", icon: UploadCloud },
  { name: "Products", href: "/products", icon: Package },
  { name: "Webhooks", href: "/webhooks", icon: Webhook },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 justify-between">
            <div className="flex">
              <div className="flex flex-shrink-0 items-center">
                <Package className="h-8 w-8 text-primary" />
                <span className="ml-2 text-xl font-semibold text-foreground">
                  Product Importer
                </span>
              </div>
              <div className="ml-10 flex space-x-8">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.href;
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={cn(
                        "inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium transition-colors",
                        isActive
                          ? "border-primary text-foreground"
                          : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
                      )}
                    >
                      <item.icon className="mr-2 h-4 w-4" />
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
}
