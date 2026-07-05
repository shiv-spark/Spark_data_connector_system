import { useState, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Upload, FolderPlus, Folder, FileText } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";

type Props = {
  connectorType: "csv" | "excel";
  onFolderResolved: (folderPath: string) => void;
  onFileResolved: (filePath: string) => void;
};


export const FolderUpload = ({ connectorType, onFolderResolved, onFileResolved }: Props) => {
  const qc = useQueryClient();
  const [browseFolder, setBrowseFolder] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const folders = useQuery({
    queryKey: ["upload_folders"],
    queryFn: async () => (await api.get("/upload_folders")).data.folders ?? [],
  });

  const currentFolder = (folders.data ?? []).find((f: any) => f.folder_name === browseFolder);

  const upload = useMutation({
    mutationFn: async ({ file, folderName }: { file: File; folderName: string }) => {
      const formData = new FormData();
      formData.append("file", file);
      const response = await api.post(`/upload_file?folder_name=${encodeURIComponent(folderName)}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return response.data;
    },
    onSuccess: (data) => {
      onFileResolved(data.file_path);
      setBrowseFolder(data.folder_name);
      setShowNewFolderInput(false);
      qc.invalidateQueries({ queryKey: ["upload_folders"] });
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const folderName = showNewFolderInput ? newFolderName.trim() : browseFolder;
    if (!folderName) {
      alert(showNewFolderInput ? "Please enter a folder name first." : "Please select a folder to upload into, or create a new one.");
      return;
    }
    upload.mutate({ file, folderName });
  };

  return (
    <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-medium text-muted-foreground">
        Browse an existing folder to pick a file or use the whole folder — or upload a new file.
      </p>

      <div className="flex items-center gap-2">
        <select
          className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
          value={browseFolder}
          onChange={(e) => setBrowseFolder(e.target.value)}
        >
          <option value="">
            {folders.isLoading ? "Loading folders..." : "Select a folder to browse"}
          </option>
          {(folders.data ?? []).map((f: any) => (
            <option key={f.folder_name} value={f.folder_name}>
              {f.folder_name} ({f.file_count} file{f.file_count === 1 ? "" : "s"})
            </option>
          ))}
        </select>
        {currentFolder && (
          <button
            type="button"
            onClick={() => onFolderResolved(currentFolder.folder_path)}
            className="whitespace-nowrap rounded-md border border-input bg-white px-3 py-2 text-sm hover:bg-slate-50"
            title="Use every file inside this folder"
          >
            <Folder className="mr-1 inline h-3.5 w-3.5" /> Use whole folder
          </button>
        )}
      </div>

      {currentFolder && (
        currentFolder.files.length > 0 ? (
          <div className="rounded-md border border-slate-200 bg-white">
            <p className="border-b border-slate-100 px-3 py-2 text-xs font-medium text-muted-foreground">
              Or pick one file from "{currentFolder.folder_name}"
            </p>
            <div className="max-h-40 overflow-auto">
              {currentFolder.files.map((fname: string) => (
                <button
                  key={fname}
                  type="button"
                  onClick={() => onFileResolved(`${currentFolder.folder_path}/${fname}`)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-emerald-50"
                >
                  <FileText className="h-3.5 w-3.5 shrink-0" />
                  {fname}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">This folder is empty — upload a file below.</p>
        )
      )}

      <div className="flex items-center gap-3">
        {showNewFolderInput ? (
          <Input
            placeholder="New folder name, e.g. sales_data"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            className="max-w-xs"
          />
        ) : (
          <button
            type="button"
            onClick={() => setShowNewFolderInput(true)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-slate-700"
          >
            <FolderPlus className="h-3.5 w-3.5" /> Or create a new folder
          </button>
        )}

        <label className="flex cursor-pointer items-center gap-2 rounded-md border border-input bg-white px-3 py-2 text-sm hover:bg-slate-50">
          <Upload className="h-4 w-4" />
          {upload.isPending ? "Uploading..." : "Upload file"}
          <input
            ref={fileInputRef}
            type="file"
            accept={connectorType === "csv" ? ".csv" : ".xlsx,.xls"}
            className="hidden"
            onChange={handleFileSelect}
            disabled={upload.isPending}
          />
        </label>
        {upload.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
        {upload.isSuccess && <span className="text-xs text-emerald-600">Uploaded: {upload.data.file_name}</span>}
        {upload.isError && <span className="text-xs text-red-500">Upload failed</span>}
      </div>
    </div>
  );
};