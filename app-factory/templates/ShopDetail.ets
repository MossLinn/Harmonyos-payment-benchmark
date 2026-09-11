// 商品详情页模板（ShopDetail）—— 页 2/5
// 数量步进 + 加入购物车（写 AppStorage.shop_cart）+ 立即购买（直接结算）
// 槽位：PRODUCTS_JSON / TASK_ID / APP_NAME
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
interface SkuOption {
  label: string
  priceDelta: number
}
interface SkuGroup {
  name: string
  options: SkuOption[]
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
struct Detail {
  @State qty: number = 1
  @State toast: string = ''
  @State skuSel: string[] = []
  @State skuErr: string = ''
  @StorageLink('detail_id') detailId: string = ''
  @StorageLink('shop_cart') cartJson: string = '[]'
  private PRODUCTS: Product[] = JSON.parse('{{PRODUCTS_JSON}}') as Product[]
  private SKU: SkuGroup[] = JSON.parse('{{SKU_JSON}}') as SkuGroup[]

  aboutToAppear(): void {
    const sel: string[] = []
    for (let i = 0; i < this.SKU.length; i++) { sel.push('') }
    this.skuSel = sel
  }

  // 已选规格的加价总和（价格 = 基础价 + Σ delta）
  skuDelta(): number {
    let d: number = 0
    for (let gi = 0; gi < this.SKU.length; gi++) {
      const label: string = this.skuSel[gi] ?? ''
      if (label === '') { continue }
      for (let oi = 0; oi < this.SKU[gi].options.length; oi++) {
        if (this.SKU[gi].options[oi].label === label) { d += this.SKU[gi].options[oi].priceDelta }
      }
    }
    return d
  }

  finalPrice(): number {
    return this.product().price + this.skuDelta()
  }

  skuSuffix(): string {
    const picked: string[] = []
    for (let gi = 0; gi < this.skuSel.length; gi++) {
      if (this.skuSel[gi] !== '') { picked.push(this.skuSel[gi]) }
    }
    if (picked.length === 0) { return '' }
    return '（' + picked.join('/') + '）'
  }

  skuAllPicked(): boolean {
    for (let gi = 0; gi < this.skuSel.length; gi++) {
      if (this.skuSel[gi] === '') { return false }
    }
    return true
  }

  pickSku(gi: number, label: string): void {
    const sel: string[] = this.skuSel.slice()
    sel[gi] = label
    this.skuSel = sel
    this.skuErr = ''
  }

  product(): Product {
    for (let i = 0; i < this.PRODUCTS.length; i++) {
      if (this.PRODUCTS[i].id === this.detailId) { return this.PRODUCTS[i] }
    }
    return this.PRODUCTS[0]
  }

  addToCart(): void {
    if (!this.skuAllPicked()) {
      this.skuErr = '请先选择全部规格'
      return
    }
    const p: Product = this.product()
    const fullName: string = p.name + this.skuSuffix()
    const price: number = this.finalPrice()
    const items: CartItem[] = JSON.parse(this.cartJson) as CartItem[]
    let found: boolean = false
    for (let i = 0; i < items.length; i++) {
      if (items[i].name === fullName) {
        items[i].qty += this.qty
        found = true
      }
    }
    if (!found) {
      items.push({ id: p.id, name: fullName, price: price, qty: this.qty, sel: true, color: p.color, emoji: p.emoji })
    }
    this.cartJson = JSON.stringify(items)
    AppStorage.setOrCreate('shop_cart', this.cartJson)
    this.toast = '已加入购物车'
  }

  buyNow(): void {
    this.addToCart()
    router.pushUrl({ url: 'pages/Checkout' })
  }

  build() {
    Column() {
      Row({ space: 10 }) {
        Text('←').fontSize(20).width(36).height(36).textAlign(TextAlign.Center)
          .onClick(() => { router.back() })
          .id('detail_back')
        Text('商品详情').fontSize(17).fontWeight(FontWeight.Bold)
      }.width('92%').margin({ top: 8 })

      Column({ space: 10 }) {
        Stack({ alignContent: Alignment.TopStart }) {
          Text(this.product().emoji).fontSize(90)
            .width('100%').height(210).textAlign(TextAlign.Center)
            .backgroundColor(this.product().color).borderRadius(14)
          if (this.product().tag !== '') {
            Text(this.product().tag).fontSize(11).fontColor('#FFFFFF')
              .backgroundColor('#E4393C').borderRadius(4).padding({ left: 6, right: 6, top: 2, bottom: 2 })
              .margin({ left: 10, top: 10 })
          }
        }
        Text(this.product().name + this.skuSuffix()).fontSize(17).fontWeight(FontWeight.Bold)
        Row() {
          Text('¥' + this.finalPrice().toFixed(2)).fontSize(22).fontColor('#E4393C').fontWeight(FontWeight.Bold)
          Blank()
          Text('已售' + this.product().sold).fontSize(11).fontColor('#999999')
        }.width('100%')
        // SKU 规格选择表单（未选完禁止加购）
        ForEach(this.SKU, (g: SkuGroup, gi: number) => {
          Column({ space: 6 }) {
            Text(g.name).fontSize(13).fontColor('#666666')
            Row({ space: 8 }) {
              ForEach(g.options, (o: SkuOption) => {
                Button(o.label + (o.priceDelta > 0 ? ` +¥${o.priceDelta}` : ''))
                  .height(34).fontSize(12)
                  .backgroundColor(this.skuSel[gi] === o.label ? '#E4393C' : '#FFFFFF')
                  .fontColor(this.skuSel[gi] === o.label ? '#FFFFFF' : '#333333')
                  .border({ width: 1, color: this.skuSel[gi] === o.label ? '#E4393C' : '#DDDDDD' })
                  .onClick(() => { this.pickSku(gi, o.label) })
              }, (o: SkuOption) => o.label)
            }
          }.width('100%').alignItems(HorizontalAlign.Start)
          .id('sku_group_' + g.name)
        }, (g: SkuGroup) => g.name)
        if (this.skuErr !== '') { Text(this.skuErr).fontSize(12).fontColor('#FF3B30').id('sku_err') }
        Row({ space: 10 }) {
          Text('数量').fontSize(14)
          Text('－').fontSize(16).width(28).height(28).textAlign(TextAlign.Center)
            .backgroundColor('#F2F3F5').borderRadius(14)
            .onClick(() => { if (this.qty > 1) { this.qty-- } })
          Text(`${this.qty}`).fontSize(15).width(30).textAlign(TextAlign.Center)
          Text('＋').fontSize(16).width(28).height(28).textAlign(TextAlign.Center)
            .backgroundColor('#F2F3F5').borderRadius(14)
            .onClick(() => { this.qty++ })
          Blank()
          Text('库存充足').fontSize(11).fontColor('#16865A')
        }.width('100%')
        if (this.toast !== '') {
          Text(this.toast).fontSize(13).fontColor('#16865A').id('added_toast')
        }
        Row({ space: 10 }) {
          Button('加入购物车').layoutWeight(1).height(46)
            .backgroundColor('#FFF0E6').fontColor('#E4393C')
            .id('add_cart')
            .onClick(() => { this.addToCart() })
          Button('立即购买').layoutWeight(1).height(46)
            .backgroundColor('#E4393C')
            .id('buy_now')
            .onClick(() => { this.buyNow() })
        }.width('100%')
        Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
      }.width('92%').padding(14).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: 10 })
    }
    .width('100%').height('100%').backgroundColor('#F5F6F8')
  }
}