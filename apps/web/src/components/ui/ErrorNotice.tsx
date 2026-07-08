export function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="rounded border border-red-800 bg-red-950/40 p-3 text-sm text-red-200">
      {message}
    </div>
  );
}
