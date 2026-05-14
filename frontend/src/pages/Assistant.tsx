import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Loader2, Send } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Message = { role: "user" | "assistant"; content: string };

export const Assistant = () => {
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [model, setModel] = useState("openai/gpt-oss-120b:free");
  const [pipelineName, setPipelineName] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);

  const chat = useMutation({
    mutationFn: async (nextMessages: Message[]) => {
      const response = await api.post("/chatbot", {
        messages: nextMessages,
        openrouter_key: openrouterKey,
        model,
        pipeline_name: pipelineName || null,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setMessages((current) => [...current, { role: "assistant", content: data.answer ?? "No answer returned." }]);
    },
    onError: (error: any) => {
      setMessages((current) => [...current, { role: "assistant", content: error?.response?.data?.detail ?? error.message }]);
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || !openrouterKey) return;
    const next = [...messages, { role: "user" as const, content: text }];
    setMessages(next);
    setInput("");
    chat.mutate(next);
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><Bot className="h-5 w-5" /> AI Assistant</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Live Pipeline Assistant</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_220px]">
            <Input type="password" placeholder="OpenRouter API key" value={openrouterKey} onChange={(e) => setOpenrouterKey(e.target.value)} />
            <Input placeholder="Model" value={model} onChange={(e) => setModel(e.target.value)} />
            <Input placeholder="Pipeline filter" value={pipelineName} onChange={(e) => setPipelineName(e.target.value)} />
          </div>
          <div className="min-h-[360px] space-y-3 rounded-md border border-slate-200 bg-slate-50 p-4">
            {messages.length === 0 ? <p className="text-sm text-muted-foreground">Ask about failures, rows loaded, slow runs, schema changes, or pipeline logs.</p> : null}
            {messages.map((message, index) => (
              <div key={index} className={message.role === "user" ? "ml-auto max-w-3xl rounded-md bg-slate-950 px-3 py-2 text-sm text-white" : "max-w-3xl whitespace-pre-wrap rounded-md border bg-white px-3 py-2 text-sm text-slate-800"}>
                {message.content}
              </div>
            ))}
            {chat.isPending ? <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Thinking...</div> : null}
          </div>
          <form onSubmit={submit} className="flex gap-3">
            <Input placeholder={openrouterKey ? "Ask about your pipeline data..." : "Enter OpenRouter key first"} value={input} onChange={(e) => setInput(e.target.value)} disabled={!openrouterKey} />
            <Button type="submit" disabled={!openrouterKey || chat.isPending}><Send /> Send</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};
