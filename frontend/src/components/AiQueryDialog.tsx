import { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Sparkles, Loader2, CheckCircle2, AlertCircle, RefreshCw, FileText, ArrowRight } from 'lucide-react';
import { generateSqlFromNaturalLanguage, type AiGenerateResponse } from '@/lib/sql-api';

interface AiQueryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectionId: string | number | null;
  connectionName: string;
  onInsert: (sql: string) => void;
}

interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  sql?: string;
}

export function AiQueryDialog({
  open,
  onOpenChange,
  connectionId,
  connectionName,
  onInsert,
}: AiQueryDialogProps) {
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [lastGeneratedSql, setLastGeneratedSql] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);

  useEffect(() => {
    if (open) {
      setInput('');
      setConversation([]);
      setLastGeneratedSql(null);
      setError(null);
      setLatency(null);
    }
  }, [open]);

  const handleGenerate = useCallback(async (question: string, isFollowUp: boolean = false) => {
    if (!connectionId || !question.trim()) return;

    setIsGenerating(true);
    setError(null);

    if (!isFollowUp) {
      setConversation([]);
      setLastGeneratedSql(null);
    }

    setConversation(prev => [...prev, { role: 'user', content: question }]);

    try {
      const response: AiGenerateResponse = await generateSqlFromNaturalLanguage({
        question,
        connection_id: String(connectionId),
        include_samples: true,
      });

      if (response.success && response.sql) {
        setLastGeneratedSql(response.sql);
        setLatency(response.llm_latency ?? null);

        let assistantMessage = response.sql;
        if (response.is_valid === false && response.validation_message) {
          assistantMessage += `\n\n[Validation: ${response.validation_message}]`;
        }

        setConversation(prev => [...prev, {
          role: 'assistant',
          content: assistantMessage,
          sql: response.sql,
        }]);
      } else {
        const errorMsg = response.error || 'Failed to generate SQL. Please try again.';
        setError(errorMsg);
        setConversation(prev => [...prev, {
          role: 'assistant',
          content: `Error: ${errorMsg}`,
        }]);
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'An unexpected error occurred';
      setError(errorMsg);
      setConversation(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${errorMsg}`,
      }]);
    } finally {
      setIsGenerating(false);
      setInput('');
    }
  }, [connectionId]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      const isFollowUp = conversation.length > 0;
      handleGenerate(input.trim(), isFollowUp);
    }
  };

  const handleInsert = () => {
    if (lastGeneratedSql) {
      onInsert(lastGeneratedSql);
      onOpenChange(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    handleGenerate(suggestion);
  };

  const suggestions = [
    "Show the top 10 customers by total sales",
    "Find all orders placed in the last 7 days",
    "Count records in each table",
    "Show columns and their data types",
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-500" />
            Generate SQL with AI
          </DialogTitle>
          <DialogDescription>
            Describe what you want to query in natural language. AI will analyze the database schema from
            <span className="font-medium text-foreground ml-1">{connectionName || 'selected connection'}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 py-4">
          {conversation.length === 0 && !isGenerating && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Try one of these suggestions:</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="text-xs px-3 py-1.5 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors border border-border"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {conversation.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-purple-600 text-white'
                    : 'bg-muted border border-border'
                }`}
              >
                {msg.sql ? (
                  <div className="space-y-2">
                    <pre className="text-sm font-mono whitespace-pre-wrap overflow-x-auto">
                      {msg.sql}
                    </pre>
                    <div className="flex items-center gap-2 text-xs opacity-70">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Generated SQL ready to insert</span>
                    </div>
                  </div>
                ) : msg.content.startsWith('Error:') ? (
                  <div className="flex items-start gap-2 text-red-500">
                    <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <span className="text-sm">{msg.content}</span>
                  </div>
                ) : (
                  <span className="text-sm">{msg.content}</span>
                )}
              </div>
            </div>
          ))}

          {isGenerating && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg px-4 py-3 border border-border">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm text-muted-foreground">
                    Analyzing schema and generating SQL...
                  </span>
                </div>
              </div>
            </div>
          )}

          {error && !isGenerating && conversation.length === 0 && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800">
              <AlertCircle className="w-4 h-4 text-red-500 mt-0.5" />
              <span className="text-sm text-red-600 dark:text-red-400">{error}</span>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="border-t pt-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={conversation.length > 0 ? "Ask a follow-up question..." : "Describe your query in natural language..."}
              className="flex-1 px-4 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              disabled={isGenerating}
            />
            <Button
              type="submit"
              disabled={!input.trim() || isGenerating}
              variant="default"
              className="bg-purple-600 hover:bg-purple-700"
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              Generate
            </Button>
          </div>
        </form>

        {lastGeneratedSql && (
          <DialogFooter className="border-t pt-4 sm:justify-between">
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {latency && <span>Generated in {latency.toFixed(2)}s</span>}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => handleGenerate(lastGeneratedSql || '', true)}
                disabled={isGenerating}
              >
                <RefreshCw className="w-4 h-4" />
                Regenerate
              </Button>
              <Button onClick={handleInsert} className="bg-green-600 hover:bg-green-700">
                <ArrowRight className="w-4 h-4" />
                Insert to Editor
              </Button>
            </div>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
