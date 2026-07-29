import { AlertCircle, Inbox } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function PageLoading() {
  return <div className="grid gap-4 md:grid-cols-3">{[1, 2, 3].map((item) => <Skeleton key={item} className="h-44 rounded-xl" />)}</div>
}

export function PageError({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <Card className="border-destructive/30">
      <CardContent className="flex min-h-44 flex-col items-center justify-center gap-3 text-center">
        <AlertCircle className="size-6 text-destructive" />
        <div><p className="font-medium">无法加载数据</p><p className="mt-1 text-sm text-muted-foreground">{error.message}</p></div>
        {retry && <Button variant="outline" onClick={retry}>重试</Button>}
      </CardContent>
    </Card>
  )
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex min-h-64 flex-col items-center justify-center gap-4 text-center">
        <div className="rounded-full bg-muted p-3"><Inbox className="size-5 text-muted-foreground" /></div>
        <div><p className="font-medium">{title}</p><p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p></div>
        {action}
      </CardContent>
    </Card>
  )
}
