// 购物应用首页模板（ShopIndex）—— top 购物 App 动线 · 页 1/5
// 页面：底部 Tab（首页商品流 / 购物车 / 我的）；搜索过滤；商品卡片（色块主图+emoji+价格+销量+标签）。
// 状态：AppStorage.shop_cart（JSON 串）为购物车唯一事实源；detail_id 传商品详情页。
// 槽位：PRODUCTS_JSON / TASK_ID / APP_NAME / FREIGHT_FREE_LINE
import { router } from '@kit.ArkUI';

interface Product {
  id: string
  name: string
  price: number
  sold: string
  tag: string
  color: string
  emoji: string
}
interface CartItem {
  id: string
  name: string
  price: number
  qty: number
  sel: boolean
  color: string
  emoji: string
}

@Entry
@Component
struct Index {
  @State tab: string = 'home'
  @State searchKey: string = ''
  @State toast: string = ''
  @StorageLink('shop_cart') cartJson: string = '[]'
  private PRODUCTS: Product[] = JSON.parse('{{PRODUCTS_JSON}}') as Product[]

  cartItems(): CartItem[] {
    return JSON.parse(this.cartJson) as CartItem[]
  }

  cartCount(): number {
    let n: number = 0
    const items: CartItem[] = this.cartItems()
    for (let i = 0; i < items.length; i++) { n += items[i].qty }
    return n
  }

  cartTotal(): number {
    let s: number = 0
    const items: CartItem[] = this.cartItems()
    for (let i = 0; i < items.length; i++) {
      if (items[i].sel) { s += items[i].price * items[i].qty }
    }
    return s
  }

  setCart(items: CartItem[]): void {
    this.cartJson = JSON.stringify(items)
    AppStorage.setOrCreate('shop_cart', this.cartJson)
  }

  toggleSel(id: string): void {
    const items: CartItem[] = this.cartItems()
    for (let i = 0; i < items.length; i++) {
      if (items[i].id === id) { items[i].sel = !items[i].sel }
    }
    this.setCart(items)
  }

  changeQty(id: string, delta: number): void {
    const items: CartItem[] = this.cartItems()
    const out: CartItem[] = []
    for (let i = 0; i < items.length; i++) {
      if (items[i].id === id) {
        items[i].qty += delta
        if (items[i].qty <= 0) { continue }  // 减到 0 = 删除
      }
      out.push(items[i])
    }
    this.setCart(out)
  }

  removeItem(id: string): void {
    const items: CartItem[] = this.cartItems()
    const out: CartItem[] = []
    for (let i = 0; i < items.length; i++) {
      if (items[i].id !== id) { out.push(items[i]) }
    }
    this.setCart(out)
  }

  selectAll(): void {
    const items: CartItem[] = this.cartItems()
    for (let i = 0; i < items.length; i++) { items[i].sel = true }
    this.setCart(items)
  }

  openDetail(p: Product): void {
    AppStorage.setOrCreate('detail_id', p.id)
    router.pushUrl({ url: 'pages/Detail' })
  }

  goSettle(): void {
    if (this.cartTotal() <= 0) {
      this.toast = '请先勾选要结算的商品'
      return
    }
    AppStorage.setOrCreate('shop_coupon', '')
    router.pushUrl({ url: 'pages/Checkout' })
  }

  filtered(): Product[] {
    if (this.searchKey === '') { return this.PRODUCTS }
    const out: Product[] = []
    for (let i = 0; i < this.PRODUCTS.length; i++) {
      if (this.PRODUCTS[i].name.includes(this.searchKey)) { out.push(this.PRODUCTS[i]) }
    }
    return out
  }

  build() {
    Column() {
      // 顶栏
      Row({ space: 10 }) {
        Text('{{APP_NAME}}').fontSize(18).fontWeight(FontWeight.Bold)
        TextInput({ placeholder: '搜索商品' })
          .height(36).layoutWeight(1)
          .fontSize(13)
          .id('search_box')
          .onChange((v: string) => { this.searchKey = v })
      }.width('92%').margin({ top: 8 })
      Text('{{TASK_ID}}').fontSize(9).fontColor('#CCCCCC').width('92%').id('task_tag')

      // 内容区
      if (this.tab === 'home') {
        Column() {
          Grid() {
            ForEach(this.filtered(), (p: Product) => {
              GridItem() {
                Column({ space: 6 }) {
                  Stack({ alignContent: Alignment.TopStart }) {
                    Text(p.emoji).fontSize(44)
                      .width('100%').height(96).textAlign(TextAlign.Center)
                      .backgroundColor(p.color).borderRadius(10)
                    if (p.tag !== '') {
                      Text(p.tag).fontSize(10).fontColor('#FFFFFF')
                        .backgroundColor('#E4393C').borderRadius(4).padding({ left: 5, right: 5, top: 2, bottom: 2 })
                        .margin({ left: 6, top: 6 })
                    }
                  }
                  Text(p.name).fontSize(13).maxLines(1)
                  Row() {
                    Text('¥' + p.price.toFixed(2)).fontSize(15).fontColor('#E4393C').fontWeight(FontWeight.Bold)
                    Blank()
                    Text(p.sold).fontSize(10).fontColor('#999999')
                  }.width('100%')
                }.padding(8).backgroundColor('#FFFFFF').borderRadius(10)
                .onClick(() => { this.openDetail(p) })
              }
            }, (p: Product) => p.id)
          }
          .columnsTemplate('1fr 1fr')
          .columnsGap(8).rowsGap(8)
          .layoutWeight(1)
          .padding(8)
          .id('product_grid')
        }.layoutWeight(1)
      } else if (this.tab === 'cart') {
        Column({ space: 8 }) {
          if (this.cartItems().length === 0) {
            Column({ space: 8 }) {
              Text('🛒').fontSize(40)
              Text('购物车是空的').fontSize(14).fontColor('#999999').id('cart_empty_marker')
            }.width('100%').margin({ top: 90 })
          } else {
            List({ space: 8 }) {
              ForEach(this.cartItems(), (it: CartItem) => {
                ListItem() {
                  Row({ space: 8 }) {
                    Checkbox().select(it.sel)
                      .onChange((v: boolean) => { if (v !== it.sel) { this.toggleSel(it.id) } })
                      .width(20)
                    Text(it.emoji).fontSize(24)
                      .width(52).height(52).textAlign(TextAlign.Center)
                      .backgroundColor(it.color).borderRadius(8)
                    Column({ space: 4 }) {
                      Text(it.name).fontSize(13).maxLines(1)
                      Text('¥' + it.price.toFixed(2)).fontSize(14).fontColor('#E4393C').fontWeight(FontWeight.Bold)
                    }.layoutWeight(1)
                    Row({ space: 8 }) {
                      Text('－').fontSize(16).width(24).height(24).textAlign(TextAlign.Center)
                        .backgroundColor('#F2F3F5').borderRadius(12)
                        .onClick(() => { this.changeQty(it.id, -1) })
                      Text(`${it.qty}`).fontSize(13).width(20).textAlign(TextAlign.Center)
                      Text('＋').fontSize(16).width(24).height(24).textAlign(TextAlign.Center)
                        .backgroundColor('#F2F3F5').borderRadius(12)
                        .onClick(() => { this.changeQty(it.id, 1) })
                      Text('删除').fontSize(12).fontColor('#999999')
                        .onClick(() => { this.removeItem(it.id) })
                    }
                  }.padding(10).backgroundColor('#FFFFFF').borderRadius(10)
                }
              }, (it: CartItem) => it.id + it.qty.toString())
            }.layoutWeight(1).width('92%')
            Row() {
              Text('全选').fontSize(12).fontColor('#1F5FD0')
                .onClick(() => { this.selectAll() })
              Blank()
              Text('合计：').fontSize(13)
              Text('¥' + this.cartTotal().toFixed(2)).fontSize(16).fontColor('#E4393C').fontWeight(FontWeight.Bold)
            }.width('92%')
            Button('去结算').width('92%').height(46)
              .backgroundColor('#E4393C')
              .id('go_settle')
              .onClick(() => { this.goSettle() })
          }
          if (this.toast !== '') { Text(this.toast).fontSize(12).fontColor('#E4393C') }
        }.layoutWeight(1).margin({ top: 8 })
      } else {
        Column({ space: 10 }) {
          Text('👤').fontSize(40).margin({ top: 80 })
          Text('{{APP_NAME}} · 测试账号').fontSize(14)
          Text('订单服务由 benchmark 元服务提供').fontSize(11).fontColor('#999999')
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
        }.width('100%').layoutWeight(1)
      }

      // 底部 Tab
      Row() {
        Text(this.tab === 'home' ? '🏠 首页' : '🏠 首页').fontSize(13)
          .fontColor(this.tab === 'home' ? '#E4393C' : '#666666')
          .layoutWeight(1).textAlign(TextAlign.Center).height(46)
          .onClick(() => { this.tab = 'home' })
        Stack({ alignContent: Alignment.TopEnd }) {
          Text('🛒 购物车').fontSize(13)
            .fontColor(this.tab === 'cart' ? '#E4393C' : '#666666')
            .width('100%').textAlign(TextAlign.Center).height(46)
            .onClick(() => { this.tab = 'cart' })
          if (this.cartCount() > 0) {
            Text(`${this.cartCount()}`).fontSize(10).fontColor('#FFFFFF')
              .backgroundColor('#E4393C').borderRadius(8).padding({ left: 4, right: 4 })
              .margin({ right: 18, top: 2 })
              .id('cart_badge')
          }
        }.layoutWeight(1)
        Text('👤 我的').fontSize(13)
          .fontColor(this.tab === 'me' ? '#E4393C' : '#666666')
          .layoutWeight(1).textAlign(TextAlign.Center).height(46)
          .onClick(() => { this.tab = 'me' })
      }.width('100%').backgroundColor('#FFFFFF').id('tab_bar')
    }
    .width('100%').height('100%').backgroundColor('#F5F6F8')
  }
}