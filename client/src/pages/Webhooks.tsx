import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Plus, ExternalLink, Trash2, Edit, PlayCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const mockWebhooks = [
  {
    id: "1",
    url: "https://api.example.com/webhook/product-created",
    event: "product.created",
    enabled: true,
  },
  {
    id: "2",
    url: "https://api.example.com/webhook/product-updated",
    event: "product.updated",
    enabled: true,
  },
  {
    id: "3",
    url: "https://api.example.com/webhook/import-completed",
    event: "import.completed",
    enabled: false,
  },
];

export default function Webhooks() {
  const [webhooks, setWebhooks] = useState(mockWebhooks);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEvent, setWebhookEvent] = useState("");
  const { toast } = useToast();

  const handleToggleWebhook = (id: string) => {
    setWebhooks((prev) =>
      prev.map((webhook) =>
        webhook.id === id ? { ...webhook, enabled: !webhook.enabled } : webhook
      )
    );
    toast({
      title: "Webhook updated",
      description: "Webhook status has been changed.",
    });
  };

  const handleTestWebhook = (url: string) => {
    toast({
      title: "Testing webhook",
      description: `Sending test request to ${url}`,
    });
    
    // Simulate test
    setTimeout(() => {
      toast({
        title: "Test successful",
        description: "Webhook responded with 200 OK (45ms)",
      });
    }, 500);
  };

  const handleAddWebhook = () => {
    if (!webhookUrl || !webhookEvent) {
      toast({
        title: "Missing information",
        description: "Please fill in all fields",
        variant: "destructive",
      });
      return;
    }

    const newWebhook = {
      id: String(webhooks.length + 1),
      url: webhookUrl,
      event: webhookEvent,
      enabled: true,
    };

    setWebhooks((prev) => [...prev, newWebhook]);
    setWebhookUrl("");
    setWebhookEvent("");
    setIsDialogOpen(false);
    
    toast({
      title: "Webhook added",
      description: "New webhook has been configured successfully.",
    });
  };

  const handleDeleteWebhook = (id: string) => {
    setWebhooks((prev) => prev.filter((webhook) => webhook.id !== id));
    toast({
      title: "Webhook deleted",
      description: "Webhook has been removed.",
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Webhooks</h1>
          <p className="mt-2 text-muted-foreground">
            Configure webhooks to receive notifications about product events
          </p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Webhook
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Webhook</DialogTitle>
              <DialogDescription>
                Configure a new webhook endpoint to receive event notifications
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="url">Webhook URL</Label>
                <Input
                  id="url"
                  placeholder="https://api.example.com/webhook"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="event">Event Type</Label>
                <Input
                  id="event"
                  placeholder="product.created"
                  value={webhookEvent}
                  onChange={(e) => setWebhookEvent(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Examples: product.created, product.updated, import.completed
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleAddWebhook}>Add Webhook</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="p-6">
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>URL</TableHead>
                <TableHead>Event</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {webhooks.map((webhook) => (
                <TableRow key={webhook.id}>
                  <TableCell className="max-w-md">
                    <div className="flex items-center space-x-2">
                      <span className="truncate font-mono text-sm">{webhook.url}</span>
                      <a
                        href={webhook.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono">
                      {webhook.event}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={webhook.enabled}
                        onCheckedChange={() => handleToggleWebhook(webhook.id)}
                      />
                      <span className="text-sm text-muted-foreground">
                        {webhook.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTestWebhook(webhook.url)}
                      >
                        <PlayCircle className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteWebhook(webhook.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  );
}
